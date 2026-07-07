"""Preview-gated GitHub Actions workflow dispatch path."""

from __future__ import annotations

import re
import typing as T
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import quote

from delegation_bot.adapter_sdk import AdapterRequest
from delegation_bot.builtin_adapters import get_builtin_adapter
from delegation_bot.evals import eval_ledger_is_valid, eval_required_adapter_evidence
from delegation_bot.harness_manifest import Manifest
from delegation_bot.harness_plan import ExecutionPlan, LedgerEvent, PlanAction


JsonMap = dict[str, T.Any]
ACTIONS_CONFIRMATION = "LIVE_GITHUB_ACTIONS"
CANCEL_CONFIRMATION = "CANCEL_GITHUB_ACTIONS"
FORCE_CANCEL_CONFIRMATION = "FORCE_CANCEL_GITHUB_ACTIONS"
GITHUB_API_VERSION = "2026-03-10"
_SENSITIVE_INPUT_RE = re.compile(r"(token|secret|password|credential|api[_-]?key)", re.IGNORECASE)
_ACTIVE_RUN_STATUSES = ("queued", "in_progress", "requested", "waiting", "pending")


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
class GitHubWorkflowMetadata:
    id: int | str
    name: str
    path: str
    state: str
    html_url: str = ""

    def to_dict(self) -> JsonMap:
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "state": self.state,
            "html_url": self.html_url,
        }


@dataclass(frozen=True)
class GitHubWorkflowRunSummary:
    id: int | str
    status: str
    conclusion: str | None = None
    event: str = ""
    head_branch: str = ""
    html_url: str = ""
    created_at: str = ""

    def to_dict(self) -> JsonMap:
        return {
            "id": self.id,
            "status": self.status,
            "conclusion": self.conclusion,
            "event": self.event,
            "head_branch": self.head_branch,
            "html_url": self.html_url,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class GitHubActionsDispatchResult:
    workflow_run_id: str = ""
    run_url: str = ""
    html_url: str = ""
    status_code: int = 0
    raw: JsonMap = field(default_factory=dict)

    def to_dict(self) -> JsonMap:
        return {
            "workflow_run_id": self.workflow_run_id,
            "run_url": self.run_url,
            "html_url": self.html_url,
            "status_code": self.status_code,
            "raw": self.raw,
        }


@dataclass(frozen=True)
class GitHubActionsCancelTarget:
    repository: str
    run_id: str
    force: bool = False

    def to_dict(self) -> JsonMap:
        details: JsonMap = {
            "repository": self.repository,
            "run_id": self.run_id,
            "force": self.force,
        }
        try:
            owner, repo = _split_repository(self.repository)
        except GitHubActionsApplyError:
            return details
        suffix = "force-cancel" if self.force else "cancel"
        details["api_path"] = f"/repos/{owner}/{repo}/actions/runs/{self.run_id}/{suffix}"
        details["actions_url"] = f"https://github.com/{self.repository}/actions/runs/{self.run_id}"
        return details


@dataclass(frozen=True)
class GitHubActionsCancelResult:
    status_code: int
    api_path: str
    force: bool = False
    raw: JsonMap = field(default_factory=dict)

    def to_dict(self) -> JsonMap:
        return {
            "status_code": self.status_code,
            "api_path": self.api_path,
            "force": self.force,
            "raw": self.raw,
        }


@dataclass(frozen=True)
class GitHubTokenDiagnostics:
    available: bool
    oauth_scopes: tuple[str, ...] = ()
    accepted_oauth_scopes: tuple[str, ...] = ()
    rate_limit_remaining: str = ""
    request_id: str = ""
    note: str = ""

    def to_dict(self) -> JsonMap:
        return {
            "available": self.available,
            "oauth_scopes": list(self.oauth_scopes),
            "accepted_oauth_scopes": list(self.accepted_oauth_scopes),
            "rate_limit_remaining": self.rate_limit_remaining,
            "request_id": self.request_id,
            "note": self.note,
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


@dataclass(frozen=True)
class GitHubActionsCancelReport:
    status: str
    apply: bool
    target: GitHubActionsCancelTarget
    gates: tuple[GitHubActionsGate, ...]
    token_diagnostics: GitHubTokenDiagnostics | None = None

    @property
    def blocked(self) -> bool:
        return any(gate.status == "blocked" for gate in self.gates)

    def to_dict(self) -> JsonMap:
        return {
            "status": self.status,
            "apply": self.apply,
            "blocked": self.blocked,
            "target": self.target.to_dict(),
            "gates": [gate.to_dict() for gate in self.gates],
            "token_diagnostics": self.token_diagnostics.to_dict() if self.token_diagnostics else None,
        }


class GitHubActionsClient:
    """Tiny GitHub REST client for gated workflow dispatch and cancellation."""

    def __init__(self, token: str, *, api_url: str = "https://api.github.com") -> None:
        if not token.strip():
            raise GitHubActionsApplyError("GITHUB_TOKEN is required for live GitHub Actions dispatch")
        self.token = token
        self.api_url = api_url.rstrip("/")

    def get_workflow(self, draft: GitHubActionsDraft) -> GitHubWorkflowMetadata:
        requests = _requests_module()
        owner, repo = _split_repository(draft.repository)
        response = requests.get(
            self._workflow_url(owner, repo, draft.workflow_ref),
            headers=self._headers(),
            timeout=20,
        )
        _raise_for_response(response)
        data = response.json()
        if not isinstance(data, dict):
            raise GitHubActionsApplyError("GitHub workflow metadata response must be a JSON object")
        return GitHubWorkflowMetadata(
            id=data.get("id") or draft.workflow_ref,
            name=str(data.get("name") or draft.workflow_ref),
            path=str(data.get("path") or ""),
            state=str(data.get("state") or ""),
            html_url=str(data.get("html_url") or ""),
        )

    def list_workflow_runs(
        self,
        draft: GitHubActionsDraft,
        *,
        status: str,
        per_page: int = 10,
    ) -> tuple[GitHubWorkflowRunSummary, ...]:
        requests = _requests_module()
        owner, repo = _split_repository(draft.repository)
        response = requests.get(
            self._workflow_url(owner, repo, draft.workflow_ref) + "/runs",
            headers=self._headers(),
            params={
                "branch": draft.ref,
                "event": "workflow_dispatch",
                "status": status,
                "per_page": per_page,
            },
            timeout=20,
        )
        _raise_for_response(response)
        data = response.json()
        runs = data.get("workflow_runs") if isinstance(data, dict) else []
        if not isinstance(runs, list):
            return ()
        return tuple(_workflow_run_summary(run) for run in runs if isinstance(run, dict))

    def active_duplicate_runs(self, draft: GitHubActionsDraft) -> tuple[GitHubWorkflowRunSummary, ...]:
        seen: set[str] = set()
        active_runs: list[GitHubWorkflowRunSummary] = []
        for status in _ACTIVE_RUN_STATUSES:
            for run in self.list_workflow_runs(draft, status=status):
                run_key = str(run.id)
                if run_key in seen:
                    continue
                seen.add(run_key)
                if _is_active_duplicate_run(run, draft):
                    active_runs.append(run)
        return tuple(active_runs)

    def dispatch_workflow(self, draft: GitHubActionsDraft) -> GitHubActionsDispatchResult:
        if len(draft.inputs) > 25:
            raise GitHubActionsApplyError("GitHub workflow_dispatch inputs are limited to 25 keys")
        requests = _requests_module()
        owner, repo = _split_repository(draft.repository)
        workflow_id = quote(draft.workflow_ref, safe="")
        payload: JsonMap = {"ref": draft.ref}
        if draft.inputs:
            payload["inputs"] = draft.inputs
        response = requests.post(
            f"{self.api_url}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
            headers=self._headers(),
            json=payload,
            timeout=20,
        )
        _raise_for_response(response)
        data: JsonMap = {}
        if getattr(response, "text", ""):
            parsed = response.json()
            data = parsed if isinstance(parsed, dict) else {}
        return GitHubActionsDispatchResult(
            workflow_run_id=str(data.get("workflow_run_id") or ""),
            run_url=str(data.get("run_url") or ""),
            html_url=str(data.get("html_url") or ""),
            status_code=int(getattr(response, "status_code", 0) or 0),
            raw=data,
        )

    def inspect_token(self) -> GitHubTokenDiagnostics:
        requests = _requests_module()
        response = requests.get(
            f"{self.api_url}/rate_limit",
            headers=self._headers(),
            timeout=20,
        )
        _raise_for_response(response)
        return _token_diagnostics_from_headers(getattr(response, "headers", {}))

    def cancel_workflow_run(self, target: GitHubActionsCancelTarget) -> GitHubActionsCancelResult:
        requests = _requests_module()
        owner, repo = _split_repository(target.repository)
        suffix = "force-cancel" if target.force else "cancel"
        api_path = f"/repos/{owner}/{repo}/actions/runs/{target.run_id}/{suffix}"
        response = requests.post(
            f"{self.api_url}{api_path}",
            headers=self._headers(),
            timeout=20,
        )
        _raise_for_response(response)
        raw: JsonMap = {}
        if getattr(response, "text", ""):
            parsed = response.json()
            raw = parsed if isinstance(parsed, dict) else {}
        return GitHubActionsCancelResult(
            status_code=int(getattr(response, "status_code", 0) or 0),
            api_path=api_path,
            force=target.force,
            raw=raw,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }

    def _workflow_url(self, owner: str, repo: str, workflow_ref: str) -> str:
        workflow_id = quote(workflow_ref, safe="")
        return f"{self.api_url}/repos/{owner}/{repo}/actions/workflows/{workflow_id}"


def build_actions_apply_report(
    manifest: Manifest,
    plan: ExecutionPlan,
    ledger_events: T.Sequence[JsonMap],
    *,
    ledger_source: str,
    apply: bool = False,
    confirmation: str | None = None,
    token: str | None = None,
    preflight_client: GitHubActionsClient | None = None,
) -> GitHubActionsApplyReport:
    """Build a gated report for GitHub Actions dispatch."""

    drafts = tuple(_github_actions_drafts(manifest, plan, ledger_events))
    gates = tuple(
        [
            _draft_gate(drafts),
            *_workflow_shape_gates(drafts),
            *_ledger_gates(ledger_events),
            _ledger_action_gate(drafts, ledger_events),
            *_policy_gates(manifest, drafts),
            *_approval_gates(manifest, ledger_events, drafts),
            _apply_intent_gate(apply, confirmation),
            _token_gate(apply, token),
            *(_live_preflight_gates(drafts, preflight_client) if apply and preflight_client else ()),
        ]
    )
    blocked = any(gate.status == "blocked" for gate in gates)
    status = "blocked" if blocked else "ready_to_dispatch" if apply else "ready"
    return GitHubActionsApplyReport(
        status=status,
        apply=apply,
        ledger_source=ledger_source,
        drafts=drafts,
        gates=gates,
        live_dispatch_supported=True,
    )


def build_actions_cancel_report(
    repository: str,
    run_id: str,
    *,
    apply: bool = False,
    force: bool = False,
    confirmation: str | None = None,
    token: str | None = None,
    token_diagnostics: GitHubTokenDiagnostics | None = None,
) -> GitHubActionsCancelReport:
    target = GitHubActionsCancelTarget(repository=repository, run_id=run_id, force=force)
    gates = tuple(
        [
            *_cancel_target_gates(target),
            _cancel_intent_gate(apply, confirmation, force=force),
            _token_gate(apply, token, operation="live workflow cancellation"),
            _token_diagnostics_gate(token_diagnostics),
        ]
    )
    blocked = any(gate.status == "blocked" for gate in gates)
    status = "blocked" if blocked else "ready_to_cancel" if apply else "ready"
    return GitHubActionsCancelReport(
        status=status,
        apply=apply,
        target=target,
        gates=gates,
        token_diagnostics=token_diagnostics,
    )


def render_actions_cancel_report(report: GitHubActionsCancelReport) -> str:
    if report.apply and report.target.force:
        mode = "force-cancel requested"
    elif report.apply:
        mode = "live cancel requested"
    else:
        mode = "preview"
    lines = [
        "GitHub Actions Cancel Gate",
        "",
        f"Status: {report.status}",
        f"Mode: {mode}",
        f"Repository: {report.target.repository}",
        f"Run id: {report.target.run_id}",
        "",
        "Gates:",
    ]
    for gate in report.gates:
        prefix = "PASS" if gate.status == "passed" else "BLOCKED"
        lines.append(f"- [{prefix}] {gate.id}: {gate.message}")
        if gate.next_action:
            lines.append(f"  next: {gate.next_action}")

    lines.extend(["", "Target:"])
    for key, value in report.target.to_dict().items():
        lines.append(f"- {key}: {value}")

    if report.token_diagnostics:
        lines.extend(["", "Token diagnostics:"])
        diagnostics = report.token_diagnostics.to_dict()
        for key in ("oauth_scopes", "accepted_oauth_scopes", "rate_limit_remaining", "request_id", "note"):
            value = diagnostics[key]
            if value:
                lines.append(f"- {key}: {value}")

    lines.extend(["", "Next:"])
    if report.blocked:
        lines.append("Fix blocked gates, then rerun the cancel preview.")
    elif report.apply:
        lines.append("Live workflow cancellation is ready to execute.")
    elif report.target.force:
        lines.append(f"Rerun with `--apply --confirm {FORCE_CANCEL_CONFIRMATION}` to force-cancel this run.")
    else:
        lines.append(f"Rerun with `--apply --confirm {CANCEL_CONFIRMATION}` to cancel this run.")
    return "\n".join(lines)


def cancel_github_actions_run(
    target: GitHubActionsCancelTarget,
    *,
    client: GitHubActionsClient,
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
                action_id=None,
                details=details or {},
            )
        )

    base_details = {
        "adapter": "github.actions",
        "repository": target.repository,
        "workflow_run_id": target.run_id,
        "force": target.force,
    }
    append_event(
        "github.actions.cancel.started",
        "executed",
        "Started GitHub Actions workflow cancellation.",
        details=base_details,
    )
    try:
        result = client.cancel_workflow_run(target)
        append_event(
            "github.actions.force_cancel.requested" if target.force else "github.actions.cancel.requested",
            "executed",
            "GitHub Actions workflow cancellation requested.",
            details={**base_details, "result": result.to_dict(), "dry_run": False},
        )
        append_event(
            "github.actions.cancel.completed",
            "passed",
            "GitHub Actions workflow cancellation completed.",
            details={**base_details, "status_code": result.status_code},
        )
    except Exception as exc:  # pragma: no cover - network failures are environment-specific
        append_event(
            "github.actions.cancel.failed",
            "failed",
            "GitHub Actions workflow cancellation failed.",
            details={**base_details, "error": str(exc)},
        )
        append_event(
            "github.actions.cancel.completed",
            "failed",
            "GitHub Actions workflow cancellation completed with errors.",
            details=base_details,
        )
    return events


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
    elif report.apply:
        lines.append("Live workflow dispatch is ready to execute.")
    else:
        lines.append(f"Rerun with `--apply --confirm {ACTIONS_CONFIRMATION}` to dispatch the workflow.")
    return "\n".join(lines)


def apply_github_actions_drafts(
    drafts: T.Sequence[GitHubActionsDraft],
    *,
    client: GitHubActionsClient,
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
        "github.actions.dispatch.started",
        "executed",
        "Started live GitHub Actions workflow dispatch.",
        details={"draft_count": len(drafts), "adapter": "github.actions"},
    )
    succeeded = 0
    for draft in drafts:
        base_details = {
            "adapter": "github.actions",
            "repository": draft.repository,
            "workflow_ref": draft.workflow_ref,
            "ref": draft.ref,
            "input_keys": list(draft.input_keys),
        }
        try:
            preflight_gates = _live_preflight_gates((draft,), client)
            blocked_preflight = [gate for gate in preflight_gates if gate.status == "blocked"]
            if blocked_preflight:
                append_event(
                    "github.actions.dispatch.blocked",
                    "blocked",
                    "GitHub Actions workflow dispatch blocked by live preflight.",
                    action_id=draft.action_id,
                    details={
                        **base_details,
                        "preflight_gates": [gate.to_dict() for gate in preflight_gates],
                    },
                )
                continue
            result = client.dispatch_workflow(draft)
            succeeded += 1
            append_event(
                "github.actions.dispatched",
                "executed",
                "GitHub Actions workflow dispatched.",
                action_id=draft.action_id,
                details={
                    **base_details,
                    "workflow_run_id": result.workflow_run_id,
                    "workflow_run_url": result.html_url or draft.workflow_run_url,
                    "run_url": result.run_url,
                    "status_code": result.status_code,
                    "cancellation": _cancellation_guidance(draft.repository, result),
                    "dry_run": False,
                },
            )
        except Exception as exc:  # pragma: no cover - network failures are environment-specific
            append_event(
                "github.actions.dispatch.failed",
                "failed",
                "GitHub Actions workflow dispatch failed.",
                action_id=draft.action_id,
                details={**base_details, "error": str(exc)},
            )

    final_status = "passed" if succeeded == len(drafts) else "failed"
    append_event(
        "github.actions.dispatch.completed",
        final_status,
        f"GitHub Actions workflow dispatch completed: {succeeded}/{len(drafts)} succeeded.",
        details={"succeeded": succeeded, "total": len(drafts), "adapter": "github.actions"},
    )
    return events


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


def _workflow_shape_gates(drafts: T.Sequence[GitHubActionsDraft]) -> list[GitHubActionsGate]:
    if not drafts:
        return [
            GitHubActionsGate("drafts.workflow_shape", "passed", "No workflow draft shape to check."),
            GitHubActionsGate("drafts.workflow_inputs", "passed", "No workflow inputs to check."),
        ]

    missing: list[str] = []
    too_many_inputs: list[str] = []
    for draft in drafts:
        missing_fields = [
            field_name
            for field_name, value in {
                "repository": draft.repository,
                "workflow_ref": draft.workflow_ref,
                "ref": draft.ref,
            }.items()
            if not value.strip()
        ]
        if missing_fields:
            missing.append(f"{draft.action_id} missing {', '.join(missing_fields)}")
        if len(draft.inputs) > 25:
            too_many_inputs.append(f"{draft.action_id} has {len(draft.inputs)} inputs")

    gates: list[GitHubActionsGate] = []
    if missing:
        gates.append(
            GitHubActionsGate(
                "drafts.workflow_shape",
                "blocked",
                "; ".join(missing) + ".",
                next_action="Set repository, workflow_ref, and ref in the github.actions executor inputs.",
            )
        )
    else:
        gates.append(
            GitHubActionsGate(
                "drafts.workflow_shape",
                "passed",
                "Every workflow draft has repository, workflow_ref, and ref.",
            )
        )

    if too_many_inputs:
        gates.append(
            GitHubActionsGate(
                "drafts.workflow_inputs",
                "blocked",
                "; ".join(too_many_inputs) + ".",
                next_action="Keep workflow_dispatch inputs at or below GitHub's 25-key limit.",
            )
        )
    else:
        gates.append(
            GitHubActionsGate(
                "drafts.workflow_inputs",
                "passed",
                "Workflow input counts are within GitHub's workflow_dispatch limit.",
            )
        )
    return gates


def _live_preflight_gates(
    drafts: T.Sequence[GitHubActionsDraft],
    client: GitHubActionsClient,
) -> tuple[GitHubActionsGate, ...]:
    gates: list[GitHubActionsGate] = []
    for draft in drafts:
        try:
            workflow = client.get_workflow(draft)
            gates.append(_workflow_metadata_gate(draft, workflow))
            if gates[-1].status == "blocked":
                continue
            duplicate_runs = client.active_duplicate_runs(draft)
            gates.append(_duplicate_run_gate(draft, duplicate_runs))
        except Exception as exc:
            gates.append(
                GitHubActionsGate(
                    f"preflight.github_api.{draft.action_id}",
                    "blocked",
                    f"GitHub preflight failed for `{draft.action_id}`: {exc}",
                    next_action="Check token permissions, repository access, workflow_ref, and network connectivity.",
                )
            )
    return tuple(gates)


def _workflow_metadata_gate(draft: GitHubActionsDraft, workflow: GitHubWorkflowMetadata) -> GitHubActionsGate:
    if workflow.state != "active":
        return GitHubActionsGate(
            f"preflight.workflow_metadata.{draft.action_id}",
            "blocked",
            f"Workflow `{draft.workflow_ref}` exists but is `{workflow.state}`.",
            next_action="Enable the workflow or choose an active workflow before dispatch.",
        )
    if not workflow.path.startswith(".github/workflows/"):
        return GitHubActionsGate(
            f"preflight.workflow_metadata.{draft.action_id}",
            "blocked",
            f"Workflow `{draft.workflow_ref}` resolved to unexpected path `{workflow.path}`.",
            next_action="Use a workflow file under `.github/workflows/`.",
        )
    return GitHubActionsGate(
        f"preflight.workflow_metadata.{draft.action_id}",
        "passed",
        f"GitHub confirmed active workflow `{workflow.path}`.",
    )


def _duplicate_run_gate(
    draft: GitHubActionsDraft,
    duplicate_runs: T.Sequence[GitHubWorkflowRunSummary],
) -> GitHubActionsGate:
    if duplicate_runs:
        run_ids = ", ".join(str(run.id) for run in duplicate_runs[:5])
        return GitHubActionsGate(
            f"preflight.duplicate_run.{draft.action_id}",
            "blocked",
            f"Active workflow_dispatch run(s) already exist for `{draft.workflow_ref}` on `{draft.ref}`: {run_ids}.",
            next_action="Wait for the active run to finish, inspect it, or cancel it before dispatching another.",
        )
    return GitHubActionsGate(
        f"preflight.duplicate_run.{draft.action_id}",
        "passed",
        f"No active workflow_dispatch run exists for `{draft.workflow_ref}` on `{draft.ref}`.",
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


def _apply_intent_gate(apply: bool, confirmation: str | None) -> GitHubActionsGate:
    if not apply:
        return GitHubActionsGate("intent.apply", "passed", "Preview mode only; no GitHub workflow dispatch will run.")
    if confirmation == ACTIONS_CONFIRMATION:
        return GitHubActionsGate("intent.apply", "passed", "Explicit live dispatch confirmation was provided.")
    return GitHubActionsGate(
        "intent.apply",
        "blocked",
        "Live dispatch requires explicit confirmation.",
        next_action=f"Use `--confirm {ACTIONS_CONFIRMATION}` with `--apply`.",
    )


def _token_gate(apply: bool, token: str | None, *, operation: str = "live dispatch") -> GitHubActionsGate:
    if not apply:
        return GitHubActionsGate("github.token", "passed", "GitHub token is not required for preview mode.")
    if token and token.strip():
        return GitHubActionsGate("github.token", "passed", f"GitHub token is available for {operation}.")
    return GitHubActionsGate(
        "github.token",
        "blocked",
        f"GITHUB_TOKEN or GH_TOKEN is required for {operation}.",
        next_action=f"Set GITHUB_TOKEN before running {operation}.",
    )


def _cancel_target_gates(target: GitHubActionsCancelTarget) -> list[GitHubActionsGate]:
    gates: list[GitHubActionsGate] = []
    try:
        _split_repository(target.repository)
    except GitHubActionsApplyError as exc:
        gates.append(
            GitHubActionsGate(
                "cancel.repository",
                "blocked",
                str(exc),
                next_action="Use repository form `owner/name`.",
            )
        )
    else:
        gates.append(
            GitHubActionsGate(
                "cancel.repository",
                "passed",
                f"Repository target is `{target.repository}`.",
            )
        )

    if target.run_id.isdigit() and int(target.run_id) > 0:
        gates.append(
            GitHubActionsGate(
                "cancel.run_id",
                "passed",
                f"Workflow run id `{target.run_id}` is valid.",
            )
        )
    else:
        gates.append(
            GitHubActionsGate(
                "cancel.run_id",
                "blocked",
                "Workflow run id must be a positive integer.",
                next_action="Copy the numeric run id from the GitHub Actions run URL.",
            )
        )
    return gates


def _cancel_intent_gate(apply: bool, confirmation: str | None, *, force: bool) -> GitHubActionsGate:
    if not apply:
        return GitHubActionsGate("intent.cancel", "passed", "Preview mode only; no GitHub workflow run will be canceled.")
    required = FORCE_CANCEL_CONFIRMATION if force else CANCEL_CONFIRMATION
    if confirmation == required:
        label = "force-cancel" if force else "cancel"
        return GitHubActionsGate("intent.cancel", "passed", f"Explicit live {label} confirmation was provided.")
    return GitHubActionsGate(
        "intent.cancel",
        "blocked",
        "Live cancellation requires explicit confirmation.",
        next_action=f"Use `--confirm {required}` with `--apply`.",
    )


def _token_diagnostics_gate(diagnostics: GitHubTokenDiagnostics | None) -> GitHubActionsGate:
    if diagnostics is None:
        return GitHubActionsGate(
            "github.token_diagnostics",
            "passed",
            "Token scope diagnostics were not run before a confirmed live operation.",
        )
    if not diagnostics.available:
        return GitHubActionsGate(
            "github.token_diagnostics",
            "blocked",
            f"Token diagnostics failed: {diagnostics.note or 'unknown error'}.",
            next_action="Check token validity and network access before live cancellation.",
        )
    if diagnostics.oauth_scopes:
        scopes = ", ".join(diagnostics.oauth_scopes)
        if "repo" in diagnostics.oauth_scopes:
            return GitHubActionsGate(
                "github.token_diagnostics",
                "passed",
                f"Classic OAuth scopes are visible and include repo: {scopes}.",
            )
        return GitHubActionsGate(
            "github.token_diagnostics",
            "passed",
            f"Classic OAuth scopes are visible but do not include repo: {scopes}.",
            next_action=(
                "For private repositories, classic tokens usually need `repo`; "
                "fine-grained tokens may not expose OAuth scopes."
            ),
        )
    return GitHubActionsGate(
        "github.token_diagnostics",
        "passed",
        "No OAuth scope header was returned; fine-grained or GitHub App tokens may omit classic scopes.",
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


def _workflow_run_summary(run: JsonMap) -> GitHubWorkflowRunSummary:
    return GitHubWorkflowRunSummary(
        id=run.get("id") or "unknown",
        status=str(run.get("status") or ""),
        conclusion=str(run.get("conclusion")) if run.get("conclusion") is not None else None,
        event=str(run.get("event") or ""),
        head_branch=str(run.get("head_branch") or ""),
        html_url=str(run.get("html_url") or ""),
        created_at=str(run.get("created_at") or ""),
    )


def _is_active_duplicate_run(run: GitHubWorkflowRunSummary, draft: GitHubActionsDraft) -> bool:
    if run.event and run.event != "workflow_dispatch":
        return False
    if run.head_branch and run.head_branch != draft.ref:
        return False
    return run.status in _ACTIVE_RUN_STATUSES


def _cancellation_guidance(repository: str, result: GitHubActionsDispatchResult) -> JsonMap:
    run_id = result.workflow_run_id
    if not run_id:
        return {
            "actions_url": f"https://github.com/{repository}/actions",
            "note": "GitHub did not return a workflow_run_id; inspect the repository Actions page.",
        }
    owner, repo = _split_repository(repository)
    return {
        "actions_url": result.html_url or f"https://github.com/{repository}/actions/runs/{run_id}",
        "cancel_api_path": f"/repos/{owner}/{repo}/actions/runs/{run_id}/cancel",
        "force_cancel_api_path": f"/repos/{owner}/{repo}/actions/runs/{run_id}/force-cancel",
        "note": "Use force-cancel only if normal cancel does not stop the run.",
    }


def _token_diagnostics_from_headers(headers: T.Mapping[str, T.Any]) -> GitHubTokenDiagnostics:
    return GitHubTokenDiagnostics(
        available=True,
        oauth_scopes=_split_header_list(str(headers.get("X-OAuth-Scopes") or "")),
        accepted_oauth_scopes=_split_header_list(str(headers.get("X-Accepted-OAuth-Scopes") or "")),
        rate_limit_remaining=str(headers.get("X-RateLimit-Remaining") or ""),
        request_id=str(headers.get("X-GitHub-Request-Id") or ""),
    )


def _split_header_list(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _split_repository(repository: str) -> tuple[str, str]:
    parts = repository.split("/", 1)
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise GitHubActionsApplyError(f"repository must be in owner/name form: {repository!r}")
    return parts[0], parts[1]


def _requests_module() -> T.Any:
    try:
        import requests
    except ImportError as exc:
        raise GitHubActionsApplyError(
            "The `requests` package is required for live GitHub Actions dispatch. "
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
    raise GitHubActionsApplyError(f"GitHub API error {response.status_code}: {payload}")
