"""Live-gated GitHub Issue apply path."""

from __future__ import annotations

import json
import os
import typing as T
from dataclasses import dataclass, field
from datetime import datetime, timezone

from delegation_bot.adapter_sdk import AdapterRequest
from delegation_bot.builtin_adapters import get_builtin_adapter
from delegation_bot.evals import (
    eval_ledger_is_valid,
    eval_no_duplicate_issue_markers,
    eval_required_adapter_evidence,
)
from delegation_bot.harness_manifest import Manifest
from delegation_bot.harness_plan import ExecutionPlan, LedgerEvent, PlanAction


JsonMap = dict[str, T.Any]
APPLY_CONFIRMATION = "LIVE_GITHUB_ISSUES"


class GitHubIssueApplyError(ValueError):
    """Raised when live GitHub Issue apply cannot proceed."""


@dataclass(frozen=True)
class ApplyGate:
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
class GitHubIssueDraft:
    action_id: str
    repository: str
    title: str
    body: str
    marker: str
    approved: bool = False
    requires_approval: bool = False

    @property
    def body_preview(self) -> str:
        return self.body[:240]

    def to_dict(self) -> JsonMap:
        return {
            "action_id": self.action_id,
            "repository": self.repository,
            "title": self.title,
            "body_preview": self.body_preview,
            "marker": self.marker,
            "approved": self.approved,
            "requires_approval": self.requires_approval,
        }


@dataclass(frozen=True)
class GitHubIssueApplyReport:
    status: str
    apply: bool
    ledger_source: str
    drafts: tuple[GitHubIssueDraft, ...]
    gates: tuple[ApplyGate, ...]

    @property
    def blocked(self) -> bool:
        return any(gate.status == "blocked" for gate in self.gates)

    def to_dict(self) -> JsonMap:
        return {
            "status": self.status,
            "apply": self.apply,
            "ledger_source": self.ledger_source,
            "blocked": self.blocked,
            "drafts": [draft.to_dict() for draft in self.drafts],
            "gates": [gate.to_dict() for gate in self.gates],
        }


class GitHubIssueClient:
    """Tiny GitHub REST client for issue create/update by marker."""

    def __init__(self, token: str, *, api_url: str = "https://api.github.com") -> None:
        if not token.strip():
            raise GitHubIssueApplyError("GITHUB_TOKEN is required for live GitHub Issue apply")
        self.token = token
        self.api_url = api_url.rstrip("/")

    def find_issue_by_marker(self, repository: str, marker: str) -> JsonMap | None:
        requests = _requests_module()
        owner, repo = _split_repository(repository)
        url = f"{self.api_url}/repos/{owner}/{repo}/issues"
        response = requests.get(
            url,
            headers=self._headers(),
            params={"state": "all", "per_page": 100},
            timeout=20,
        )
        _raise_for_response(response)
        issues = response.json()
        if not isinstance(issues, list):
            return None
        for issue in issues:
            if not isinstance(issue, dict) or "pull_request" in issue:
                continue
            body = issue.get("body") if isinstance(issue.get("body"), str) else ""
            if marker in body:
                return issue
        return None

    def create_issue(self, repository: str, title: str, body: str) -> JsonMap:
        requests = _requests_module()
        owner, repo = _split_repository(repository)
        response = requests.post(
            f"{self.api_url}/repos/{owner}/{repo}/issues",
            headers=self._headers(),
            json={"title": title, "body": body},
            timeout=20,
        )
        _raise_for_response(response)
        data = response.json()
        return data if isinstance(data, dict) else {}

    def update_issue(self, repository: str, number: int, title: str, body: str) -> JsonMap:
        requests = _requests_module()
        owner, repo = _split_repository(repository)
        response = requests.patch(
            f"{self.api_url}/repos/{owner}/{repo}/issues/{number}",
            headers=self._headers(),
            json={"title": title, "body": body},
            timeout=20,
        )
        _raise_for_response(response)
        data = response.json()
        return data if isinstance(data, dict) else {}

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }


def build_apply_report(
    manifest: Manifest,
    plan: ExecutionPlan,
    ledger_events: T.Sequence[JsonMap],
    *,
    ledger_source: str,
    apply: bool = False,
    confirmation: str | None = None,
    token: str | None = None,
) -> GitHubIssueApplyReport:
    drafts = tuple(_github_issue_drafts(manifest, plan, ledger_events, ledger_source=ledger_source))
    gates = tuple(
        [
            _draft_gate(drafts),
            *_ledger_gates(ledger_events),
            *_policy_gates(manifest, drafts),
            *_approval_gates(manifest, ledger_events, drafts),
            _apply_intent_gate(apply, confirmation),
            _token_gate(apply, token),
        ]
    )
    blocked = any(gate.status == "blocked" for gate in gates)
    status = "blocked" if blocked else "ready" if not apply else "ready_to_apply"
    return GitHubIssueApplyReport(
        status=status,
        apply=apply,
        ledger_source=ledger_source,
        drafts=drafts,
        gates=gates,
    )


def render_apply_report(report: GitHubIssueApplyReport) -> str:
    lines = [
        "GitHub Issue Apply Gate",
        "",
        f"Status: {report.status}",
        f"Mode: {'live apply' if report.apply else 'preview'}",
        f"Ledger: {report.ledger_source}",
        f"Issue drafts: {len(report.drafts)}",
        "",
        "Gates:",
    ]
    for gate in report.gates:
        prefix = "PASS" if gate.status == "passed" else "BLOCKED"
        lines.append(f"- [{prefix}] {gate.id}: {gate.message}")
        if gate.next_action:
            lines.append(f"  next: {gate.next_action}")

    lines.extend(["", "Issue drafts:"])
    if report.drafts:
        for draft in report.drafts:
            approval = " approval-required" if draft.requires_approval else ""
            lines.append(f"- {draft.repository}: {draft.title}{approval}")
            lines.append(f"  marker: {draft.marker}")
            lines.append(f"  action: {draft.action_id}")
    else:
        lines.append("- none")

    lines.extend(["", "Next:"])
    if report.blocked:
        lines.append("Fix blocked gates, then rerun the preview.")
    elif report.apply:
        lines.append("Live apply is ready to execute.")
    else:
        lines.append(f"Rerun with `--apply --confirm {APPLY_CONFIRMATION}` to write GitHub Issues.")
    return "\n".join(lines)


def _draft_gate(drafts: T.Sequence[GitHubIssueDraft]) -> ApplyGate:
    if drafts:
        return ApplyGate("drafts.github_issue", "passed", f"{len(drafts)} GitHub Issue draft(s) found.")
    return ApplyGate(
        "drafts.github_issue",
        "blocked",
        "No github.issue executor actions were found.",
        next_action="Add a github.issue executor or choose a Harnessfile with issue output.",
    )


def apply_github_issue_drafts(
    drafts: T.Sequence[GitHubIssueDraft],
    *,
    client: GitHubIssueClient,
    run_id: str,
    start_sequence: int,
    timestamp: str | None = None,
) -> list[LedgerEvent]:
    event_time = timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    events: list[LedgerEvent] = []

    def append_event(
        event_type: str,
        status: str,
        message: str,
        action_id: str | None = None,
        details: JsonMap | None = None,
    ) -> None:
        events.append(
            LedgerEvent(
                run_id=run_id,
                sequence=start_sequence + len(events),
                timestamp=event_time,
                type=event_type,
                status=status,
                message=message,
                action_id=action_id,
                details=details or {},
            )
        )

    append_event(
        "github.issue.apply.started",
        "running",
        "Started live GitHub Issue apply.",
        details={"draft_count": len(drafts), "adapter": "github.issue"},
    )
    succeeded = 0
    for draft in drafts:
        base_details = {
            "adapter": "github.issue",
            "repository": draft.repository,
            "issue_marker": draft.marker,
            "title": draft.title,
            "body_preview": draft.body_preview,
        }
        try:
            existing = client.find_issue_by_marker(draft.repository, draft.marker)
            if existing and isinstance(existing.get("number"), int):
                issue = client.update_issue(draft.repository, existing["number"], draft.title, draft.body)
                operation = "updated"
            else:
                issue = client.create_issue(draft.repository, draft.title, draft.body)
                operation = "created"
            succeeded += 1
            append_event(
                f"github.issue.{operation}",
                "executed",
                f"GitHub Issue {operation}.",
                action_id=draft.action_id,
                details={
                    **base_details,
                    "operation": operation,
                    "issue_number": issue.get("number"),
                    "issue_url": issue.get("html_url"),
                },
            )
        except Exception as exc:  # pragma: no cover - network failures are environment-specific
            append_event(
                "github.issue.apply.failed",
                "failed",
                "GitHub Issue apply failed.",
                action_id=draft.action_id,
                details={**base_details, "error": str(exc)},
            )

    final_status = "succeeded" if succeeded == len(drafts) else "failed"
    append_event(
        "github.issue.apply.completed",
        final_status,
        f"GitHub Issue apply completed: {succeeded}/{len(drafts)} succeeded.",
        details={"succeeded": succeeded, "total": len(drafts), "adapter": "github.issue"},
    )
    return events


def github_token_from_env() -> str | None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    return token if isinstance(token, str) and token.strip() else None


def _github_issue_drafts(
    manifest: Manifest,
    plan: ExecutionPlan,
    ledger_events: T.Sequence[JsonMap],
    *,
    ledger_source: str,
) -> T.Iterator[GitHubIssueDraft]:
    adapter = get_builtin_adapter("github.issue")
    if adapter is None:
        raise GitHubIssueApplyError("github.issue adapter is required")
    approved_action_ids = _approved_action_ids(ledger_events)
    for action in plan.actions:
        if action.adapter != "github.issue" or not action.type.startswith("adapter.github.issue."):
            continue
        inputs = _executor_inputs(action)
        request = AdapterRequest(
            adapter_id="github.issue",
            action_id=action.id,
            mission_id=plan.id,
            objective=plan.objective,
            inputs=inputs,
            metadata={"action": action.to_dict()},
            dry_run=True,
        )
        dry_run_result = adapter.plan(request)
        issue = dry_run_result.outputs.get("github.issue", {})
        marker = str(dry_run_result.evidence.get("issue_marker") or issue.get("issue_marker") or "")
        repository = str(inputs.get("repository") or "")
        title = str(inputs.get("issue_title") or "DelegationHQ Issue")
        body = str(inputs.get("issue_body") or "")
        body = _body_with_marker_and_ledger(body, marker, ledger_source)
        yield GitHubIssueDraft(
            action_id=action.id,
            repository=repository,
            title=title,
            body=body,
            marker=marker,
            approved=action.id in approved_action_ids,
            requires_approval=action.requires_approval,
        )


def _executor_inputs(action: PlanAction) -> JsonMap:
    executor = action.metadata.get("executor")
    if not isinstance(executor, dict):
        return {}
    inputs = executor.get("inputs")
    return dict(inputs) if isinstance(inputs, dict) else {}


def _body_with_marker_and_ledger(body: str, marker: str, ledger_source: str) -> str:
    lines: list[str] = []
    if marker and marker not in body:
        lines.extend([f"<!-- {marker} -->", ""])
    lines.append(body.strip() or "DelegationHQ planned this GitHub Issue.")
    lines.extend(
        [
            "",
            "---",
            "",
            "DelegationHQ live apply evidence:",
            f"- source ledger: `{ledger_source}`",
            "- adapter: `github.issue`",
        ]
    )
    return "\n".join(lines)


def _ledger_gates(ledger_events: T.Sequence[JsonMap]) -> list[ApplyGate]:
    evals = [
        eval_ledger_is_valid(ledger_events),
        eval_no_duplicate_issue_markers(ledger_events),
        eval_required_adapter_evidence(ledger_events),
    ]
    gates: list[ApplyGate] = []
    for result in evals:
        gates.append(
            ApplyGate(
                id=f"eval.{result.id}",
                status="passed" if result.status == "passed" else "blocked",
                message=result.message,
                next_action=None if result.status == "passed" else "Run dry-run planning and evals before apply.",
            )
        )
    return gates


def _policy_gates(manifest: Manifest, drafts: T.Sequence[GitHubIssueDraft]) -> list[ApplyGate]:
    allowed = _allowed_repositories(manifest)
    if not allowed:
        return [
            ApplyGate(
                id="policy.allowed_repositories",
                status="blocked",
                message="No allowed repositories are declared.",
                next_action="Add policies.permissions.allowed_repositories before live apply.",
            )
        ]
    blocked = sorted({draft.repository for draft in drafts if draft.repository not in allowed})
    if blocked:
        return [
            ApplyGate(
                id="policy.allowed_repositories",
                status="blocked",
                message=f"Repository not allowed: {', '.join(blocked)}.",
                next_action="Update the Harnessfile repository policy or issue executor input.",
            )
        ]
    return [
        ApplyGate(
            id="policy.allowed_repositories",
            status="passed",
            message="All issue repositories are allowed by policy.",
        )
    ]


def _approval_gates(
    manifest: Manifest,
    ledger_events: T.Sequence[JsonMap],
    drafts: T.Sequence[GitHubIssueDraft],
) -> list[ApplyGate]:
    approvals_required = _approval_required_for_github_issue(manifest)
    if not approvals_required:
        return [ApplyGate("approval.github_issue", "passed", "GitHub Issue apply does not require approval by policy.")]
    approved_action_ids = _approved_action_ids(ledger_events)
    missing = [draft.action_id for draft in drafts if draft.action_id not in approved_action_ids]
    if missing:
        return [
            ApplyGate(
                "approval.github_issue",
                "blocked",
                f"Approval evidence is missing for {len(missing)} GitHub Issue action(s).",
                next_action="Append approval.granted ledger evidence before live apply.",
            )
        ]
    return [ApplyGate("approval.github_issue", "passed", "Approval evidence exists for GitHub Issue apply.")]


def _apply_intent_gate(apply: bool, confirmation: str | None) -> ApplyGate:
    if not apply:
        return ApplyGate("intent.apply", "passed", "Preview mode only; no live writes will run.")
    if confirmation == APPLY_CONFIRMATION:
        return ApplyGate("intent.apply", "passed", "Explicit live apply confirmation was provided.")
    return ApplyGate(
        "intent.apply",
        "blocked",
        "Live apply requires explicit confirmation.",
        next_action=f"Use `--confirm {APPLY_CONFIRMATION}` with `--apply`.",
    )


def _token_gate(apply: bool, token: str | None) -> ApplyGate:
    if not apply:
        return ApplyGate("github.token", "passed", "GitHub token is not required for preview mode.")
    if token and token.strip():
        return ApplyGate("github.token", "passed", "GitHub token is available for live apply.")
    return ApplyGate(
        "github.token",
        "blocked",
        "GITHUB_TOKEN or GH_TOKEN is required for live apply.",
        next_action="Set GITHUB_TOKEN before running live apply.",
    )


def _allowed_repositories(manifest: Manifest) -> set[str]:
    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
    permissions = policies.get("permissions") if isinstance(policies.get("permissions"), dict) else {}
    repositories = permissions.get("allowed_repositories") if isinstance(permissions.get("allowed_repositories"), list) else []
    return {str(item) for item in repositories if isinstance(item, str) and item.strip()}


def _approval_required_for_github_issue(manifest: Manifest) -> bool:
    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
    approvals = policies.get("approvals") if isinstance(policies.get("approvals"), dict) else {}
    required_for = approvals.get("required_for") if isinstance(approvals.get("required_for"), list) else []
    aliases = {"github_issue", "issue", "github.issue"}
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


def _split_repository(repository: str) -> tuple[str, str]:
    parts = repository.split("/", 1)
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise GitHubIssueApplyError(f"repository must be in owner/name form: {repository!r}")
    return parts[0], parts[1]


def _requests_module() -> T.Any:
    try:
        import requests
    except ImportError as exc:
        raise GitHubIssueApplyError(
            "The `requests` package is required for live GitHub Issue apply. "
            "Install dependencies with `python -m pip install -r requirements.txt`."
        ) from exc
    return requests


def _raise_for_response(response: T.Any) -> None:
    if response.status_code < 400:
        return
    try:
        payload = response.json()
    except ValueError:
        payload = response.text
    raise GitHubIssueApplyError(f"GitHub API error {response.status_code}: {payload}")
