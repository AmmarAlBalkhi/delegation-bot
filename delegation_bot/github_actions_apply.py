"""Preview-gated GitHub Actions workflow dispatch path."""

from __future__ import annotations

import re
import typing as T
from dataclasses import dataclass, field

from delegation_bot.adapter_sdk import AdapterRequest
from delegation_bot.builtin_adapters import get_builtin_adapter
from delegation_bot.evals import eval_ledger_is_valid, eval_required_adapter_evidence
from delegation_bot.harness_manifest import Manifest
from delegation_bot.harness_plan import ExecutionPlan, PlanAction


JsonMap = dict[str, T.Any]
ACTIONS_CONFIRMATION = "LIVE_GITHUB_ACTIONS"
_SENSITIVE_INPUT_RE = re.compile(r"(token|secret|password|credential|api[_-]?key)", re.IGNORECASE)


class GitHubActionsApplyError(ValueError):
    """Raised when GitHub Actions dispatch preview cannot be built."""


@dataclass(frozen=True)
class GitHubActionsGate:
    id: str
    status: str
    message: str
    next_action: str | None = None

    def to_dict(self) -> JsonMap:
        return {
            "id": self.id,
            "status": self.status,
            "message": self.message,
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class GitHubActionsDraft:
    action_id: str
    repository: str
    workflow_ref: str
    ref: str
    inputs: JsonMap = field(default_factory=dict)
    workflow_run_id: str = ""
    workflow_run_url: str = ""
    approved: bool = False
    requires_approval: bool = False

    @property
    def input_keys(self) -> tuple[str, ...]:
        return tuple(sorted(str(key) for key in self.inputs))

    def to_dict(self) -> JsonMap:
        return {
            "action_id": self.action_id,
            "repository": self.repository,
            "workflow_ref": self.workflow_ref,
            "ref": self.ref,
            "input_keys": list(self.input_keys),
            "inputs": _redacted_inputs(self.inputs),
            "workflow_run_id": self.workflow_run_id,
            "workflow_run_url": self.workflow_run_url,
            "approved": self.approved,
            "requires_approval": self.requires_approval,
        }


@dataclass(frozen=True)
class GitHubActionsApplyReport:
    status: str
    apply: bool
    ledger_source: str
    drafts: tuple[GitHubActionsDraft, ...]
    gates: tuple[GitHubActionsGate, ...]
    live_dispatch_supported: bool = False

    @property
    def blocked(self) -> bool:
        return any(gate.status == "blocked" for gate in self.gates)

    def to_dict(self) -> JsonMap:
        return {
            "status": self.status,
            "apply": self.apply,
            "ledger_source": self.ledger_source,
            "blocked": self.blocked,
            "live_dispatch_supported": self.live_dispatch_supported,
            "drafts": [draft.to_dict() for draft in self.drafts],
            "gates": [gate.to_dict() for gate in self.gates],
        }


def build_actions_apply_report(
    manifest: Manifest,
    plan: ExecutionPlan,
    ledger_events: T.Sequence[JsonMap],
    *,
    ledger_source: str,
    apply: bool = False,
    confirmation: str | None = None,
    token: str | None = None,
) -> GitHubActionsApplyReport:
    """Build a preview report for GitHub Actions dispatch.

    Live dispatch is intentionally not implemented yet. This report is the
    product step before that: it shows the workflow draft and the gates that
    must pass before a future dispatch client can be trusted.
    """

    drafts = tuple(_github_actions_drafts(manifest, plan, ledger_events))
    gates = tuple(
        [
            _draft_gate(drafts),
            *_ledger_gates(ledger_events),
            _ledger_action_gate(drafts, ledger_events),
            *_policy_gates(manifest, drafts),
            *_approval_gates(manifest, ledger_events, drafts),
            _dispatch_support_gate(apply),
            _apply_intent_gate(apply, confirmation),
            _token_gate(apply, token),
        ]
    )
    blocked = any(gate.status == "blocked" for gate in gates)
    status = "blocked" if blocked else "ready"
    return GitHubActionsApplyReport(
        status=status,
        apply=apply,
        ledger_source=ledger_source,
        drafts=drafts,
        gates=gates,
    )


def render_actions_apply_report(report: GitHubActionsApplyReport) -> str:
    lines = [
        "GitHub Actions Apply Gate",
        "",
        f"Status: {report.status}",
        f"Mode: {'live dispatch requested' if report.apply else 'preview'}",
        f"Ledger: {report.ledger_source}",
        f"Workflow drafts: {len(report.drafts)}",
        "",
        "Gates:",
    ]
    for gate in report.gates:
        prefix = "PASS" if gate.status == "passed" else "BLOCKED"
        lines.append(f"- [{prefix}] {gate.id}: {gate.message}")
        if gate.next_action:
            lines.append(f"  next: {gate.next_action}")

    lines.extend(["", "Workflow drafts:"])
    if report.drafts:
        for draft in report.drafts:
            approval = " approval-required" if draft.requires_approval else ""
            inputs = _format_inputs(draft.inputs)
            lines.append(f"- {draft.repository}: {draft.workflow_ref} @ {draft.ref}{approval}")
            lines.append(f"  action: {draft.action_id}")
            lines.append(f"  run: {draft.workflow_run_url}")
            lines.append(f"  inputs: {inputs}")
    else:
        lines.append("- none")

    lines.extend(["", "Next:"])
    if report.blocked:
        lines.append("Fix blocked gates, then rerun the preview.")
    else:
        lines.append(
            "Use this preview as dispatch evidence. Live GitHub Actions dispatch remains locked until the future live client is implemented."
        )
    return "\n".join(lines)


def _github_actions_drafts(
    manifest: Manifest,
    plan: ExecutionPlan,
    ledger_events: T.Sequence[JsonMap],
) -> T.Iterator[GitHubActionsDraft]:
    adapter = get_builtin_adapter("github.actions")
    if adapter is None:
        raise GitHubActionsApplyError("github.actions adapter is required")
    approved_action_ids = _approved_action_ids(ledger_events)
    for action in plan.actions:
        if action.adapter != "github.actions" or not action.type.startswith("adapter.github.actions."):
            continue
        inputs = _executor_inputs(action)
        request = AdapterRequest(
            adapter_id="github.actions",
            action_id=action.id,
            mission_id=plan.id,
            objective=plan.objective,
            inputs=inputs,
            metadata={"action": action.to_dict()},
            dry_run=True,
        )
        result = adapter.plan(request)
        workflow_run = result.outputs.get("workflow_run") if isinstance(result.outputs.get("workflow_run"), dict) else {}
        yield GitHubActionsDraft(
            action_id=action.id,
            repository=str(inputs.get("repository") or workflow_run.get("repository") or ""),
            workflow_ref=str(inputs.get("workflow_ref") or workflow_run.get("workflow_ref") or ""),
            ref=str(inputs.get("ref") or workflow_run.get("ref") or "main"),
            inputs=_workflow_inputs(inputs),
            workflow_run_id=str(result.evidence.get("workflow_run_id") or workflow_run.get("workflow_run_id") or ""),
            workflow_run_url=str(result.evidence.get("workflow_run_url") or workflow_run.get("workflow_run_url") or ""),
            approved=action.id in approved_action_ids,
            requires_approval=action.requires_approval,
        )


def _draft_gate(drafts: T.Sequence[GitHubActionsDraft]) -> GitHubActionsGate:
    if drafts:
        return GitHubActionsGate(
            "drafts.github_actions",
            "passed",
            f"{len(drafts)} GitHub Actions workflow draft(s) found.",
        )
    return GitHubActionsGate(
        "drafts.github_actions",
        "blocked",
        "No github.actions executor actions were found.",
        next_action="Add a github.actions executor or choose a Harnessfile with workflow verification.",
    )


def _ledger_gates(ledger_events: T.Sequence[JsonMap]) -> list[GitHubActionsGate]:
    evals = [
        eval_ledger_is_valid(ledger_events),
        eval_required_adapter_evidence(ledger_events),
    ]
    gates: list[GitHubActionsGate] = []
    for result in evals:
        gates.append(
            GitHubActionsGate(
                id=f"eval.{result.id}",
                status="passed" if result.status == "passed" else "blocked",
                message=result.message,
                next_action=None if result.status == "passed" else "Run dry-run planning and evals before dispatch preview.",
            )
        )
    return gates


def _ledger_action_gate(
    drafts: T.Sequence[GitHubActionsDraft],
    ledger_events: T.Sequence[JsonMap],
) -> GitHubActionsGate:
    if not drafts:
        return GitHubActionsGate("ledger.github_actions_evidence", "passed", "No workflow drafts need ledger matching.")
    evidence_by_action = _workflow_evidence_by_action(ledger_events)
    missing_actions = [draft.action_id for draft in drafts if draft.action_id not in evidence_by_action]
    missing_urls = [
        draft.action_id
        for draft in drafts
        if draft.action_id in evidence_by_action and not evidence_by_action[draft.action_id].get("workflow_run_url")
    ]
    if missing_actions or missing_urls:
        parts: list[str] = []
        if missing_actions:
            parts.append(f"missing action evidence: {', '.join(missing_actions)}")
        if missing_urls:
            parts.append(f"missing workflow run URLs: {', '.join(missing_urls)}")
        return GitHubActionsGate(
            "ledger.github_actions_evidence",
            "blocked",
            "; ".join(parts) + ".",
            next_action="Rerun dry-run planning so the ledger includes github.actions evidence.",
        )
    return GitHubActionsGate(
        "ledger.github_actions_evidence",
        "passed",
        "Every workflow draft has matching ledger evidence and a run URL preview.",
    )


def _policy_gates(manifest: Manifest, drafts: T.Sequence[GitHubActionsDraft]) -> list[GitHubActionsGate]:
    if not drafts:
        return [GitHubActionsGate("policy.allowed_repositories", "passed", "No workflow repositories to check.")]
    allowed = _allowed_repositories(manifest)
    if not allowed:
        return [
            GitHubActionsGate(
                id="policy.allowed_repositories",
                status="blocked",
                message="No allowed repositories are declared.",
                next_action="Add policies.permissions.allowed_repositories before workflow dispatch.",
            )
        ]
    blocked = sorted({draft.repository for draft in drafts if draft.repository not in allowed})
    if blocked:
        return [
            GitHubActionsGate(
                id="policy.allowed_repositories",
                status="blocked",
                message=f"Repository not allowed: {', '.join(blocked)}.",
                next_action="Update the Harnessfile repository policy or workflow executor input.",
            )
        ]
    return [
        GitHubActionsGate(
            id="policy.allowed_repositories",
            status="passed",
            message="All workflow repositories are allowed by policy.",
        )
    ]


def _approval_gates(
    manifest: Manifest,
    ledger_events: T.Sequence[JsonMap],
    drafts: T.Sequence[GitHubActionsDraft],
) -> list[GitHubActionsGate]:
    approvals_required = _approval_required_for_github_actions(manifest) or any(draft.requires_approval for draft in drafts)
    if not approvals_required:
        return [
            GitHubActionsGate(
                "approval.github_actions",
                "passed",
                "GitHub Actions dispatch does not require approval by policy.",
            )
        ]
    approved_action_ids = _approved_action_ids(ledger_events)
    missing = [draft.action_id for draft in drafts if draft.action_id not in approved_action_ids]
    if missing:
        return [
            GitHubActionsGate(
                "approval.github_actions",
                "blocked",
                f"Approval evidence is missing for {len(missing)} GitHub Actions workflow action(s).",
                next_action="Append approval.granted ledger evidence before workflow dispatch.",
            )
        ]
    return [GitHubActionsGate("approval.github_actions", "passed", "Approval evidence exists for GitHub Actions dispatch.")]


def _dispatch_support_gate(apply: bool) -> GitHubActionsGate:
    if not apply:
        return GitHubActionsGate(
            "dispatch.live_supported",
            "passed",
            "Preview mode only; live workflow dispatch is locked.",
        )
    return GitHubActionsGate(
        "dispatch.live_supported",
        "blocked",
        "Live GitHub Actions dispatch is not implemented yet.",
        next_action="Use this preview as evidence, then implement the live dispatch client behind the same gates.",
    )


def _apply_intent_gate(apply: bool, confirmation: str | None) -> GitHubActionsGate:
    if not apply:
        return GitHubActionsGate("intent.apply", "passed", "Preview mode only; no GitHub workflow dispatch will run.")
    if confirmation == ACTIONS_CONFIRMATION:
        return GitHubActionsGate("intent.apply", "passed", "Explicit live dispatch confirmation was provided.")
    return GitHubActionsGate(
        "intent.apply",
        "blocked",
        "Live dispatch requires explicit confirmation.",
        next_action=f"Use `--confirm {ACTIONS_CONFIRMATION}` with `--apply` after live dispatch exists.",
    )


def _token_gate(apply: bool, token: str | None) -> GitHubActionsGate:
    if not apply:
        return GitHubActionsGate("github.token", "passed", "GitHub token is not required for preview mode.")
    if token and token.strip():
        return GitHubActionsGate("github.token", "passed", "GitHub token is available for live dispatch.")
    return GitHubActionsGate(
        "github.token",
        "blocked",
        "GITHUB_TOKEN or GH_TOKEN is required for live dispatch.",
        next_action="Set GITHUB_TOKEN before a future live dispatch run.",
    )


def _executor_inputs(action: PlanAction) -> JsonMap:
    executor = action.metadata.get("executor")
    if not isinstance(executor, dict):
        return {}
    inputs = executor.get("inputs")
    return dict(inputs) if isinstance(inputs, dict) else {}


def _workflow_inputs(inputs: JsonMap) -> JsonMap:
    workflow_inputs = inputs.get("inputs")
    return dict(workflow_inputs) if isinstance(workflow_inputs, dict) else {}


def _workflow_evidence_by_action(events: T.Sequence[JsonMap]) -> dict[str, JsonMap]:
    evidence_by_action: dict[str, JsonMap] = {}
    for event in events:
        action_id = event.get("action_id")
        if not isinstance(action_id, str) or not action_id.strip():
            continue
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        adapter = details.get("adapter")
        event_type = event.get("type") if isinstance(event.get("type"), str) else ""
        if adapter != "github.actions" and not event_type.startswith("github.actions") and not event_type.startswith(
            "adapter.github.actions"
        ):
            continue
        adapter_result = details.get("adapter_result") if isinstance(details.get("adapter_result"), dict) else {}
        evidence = adapter_result.get("evidence") if isinstance(adapter_result.get("evidence"), dict) else {}
        if evidence:
            evidence_by_action.setdefault(action_id, {}).update(evidence)
    return evidence_by_action


def _allowed_repositories(manifest: Manifest) -> set[str]:
    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
    permissions = policies.get("permissions") if isinstance(policies.get("permissions"), dict) else {}
    repositories = permissions.get("allowed_repositories") if isinstance(permissions.get("allowed_repositories"), list) else []
    return {str(item) for item in repositories if isinstance(item, str) and item.strip()}


def _approval_required_for_github_actions(manifest: Manifest) -> bool:
    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
    approvals = policies.get("approvals") if isinstance(policies.get("approvals"), dict) else {}
    required_for = approvals.get("required_for") if isinstance(approvals.get("required_for"), list) else []
    aliases = {"github_actions", "github.actions", "workflow", "workflow_dispatch", "actions"}
    return any(str(item) in aliases for item in required_for)


def _approved_action_ids(events: T.Sequence[JsonMap]) -> set[str]:
    approved: set[str] = set()
    for event in events:
        if event.get("type") != "approval.granted":
            continue
        action_id = event.get("action_id")
        if isinstance(action_id, str) and action_id.strip():
            approved.add(action_id)
    return approved


def _redacted_inputs(inputs: JsonMap) -> JsonMap:
    redacted: JsonMap = {}
    for key, value in inputs.items():
        key_text = str(key)
        redacted[key_text] = "[redacted]" if _SENSITIVE_INPUT_RE.search(key_text) else value
    return redacted


def _format_inputs(inputs: JsonMap) -> str:
    redacted = _redacted_inputs(inputs)
    if not redacted:
        return "none"
    return ", ".join(f"{key}={redacted[key]!r}" for key in sorted(redacted))
