#!/usr/bin/env python3
"""Human-readable approval preview cards for agent actions."""

from __future__ import annotations

import typing as T
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from delegation_bot.agent_gate import AgentGateReport, build_agent_gate_report
from delegation_bot.harness_manifest import Manifest, ManifestError, load_manifest, validate_manifest
from delegation_bot.ledger import LedgerError, load_ledger_events
from delegation_bot.local_workspace import (
    DEFAULT_WORKSPACE_AGENT_RUN_LEDGER,
    DEFAULT_WORKSPACE_HARNESS,
    DEFAULT_WORKSPACE_REGISTRY,
)


JsonMap = dict[str, T.Any]
APPROVAL_PREVIEW_SCHEMA_VERSION = "delegation.approval-preview.v1"


@dataclass(frozen=True)
class ApprovalPreviewReport:
    status: str
    workspace: str | None
    ledger: str | None
    agent_id: str
    action: str
    target: str
    gate: AgentGateReport
    summary: str
    can_execute: bool
    command: str | None
    reviewer_note: str | None = None
    expires_at: str | None = None
    expired: bool = False
    request_context: JsonMap | None = None
    resource_summary: JsonMap | None = None
    evidence_status: JsonMap | None = None
    history: JsonMap | None = None
    warnings: tuple[str, ...] = ()

    @property
    def action_id(self) -> str:
        return f"agent_gate.{_event_id_part(self.agent_id)}.{_event_id_part(self.action)}"

    @property
    def required_approvals(self) -> tuple[str, ...]:
        return self.gate.matched_approvals or self.gate.required_approvals

    @property
    def missing_approvals(self) -> tuple[str, ...]:
        if self.gate.decision != "approval_required":
            return ()
        if self.gate.matched_approvals:
            return tuple(item for item in self.gate.matched_approvals if item not in self.gate.provided_approvals)
        return ("human.approval",)

    @property
    def next_actions(self) -> tuple[str, ...]:
        actions: list[str] = []
        if self.workspace:
            actions.append(
                f"delegation agent-gate --registry {Path(self.workspace) / DEFAULT_WORKSPACE_REGISTRY} "
                f"{self.agent_id} --action {self.action} --target {self.target}"
            )
        if self.gate.decision == "allow" and self.workspace:
            actions.append(
                f"delegation agent-run {self.agent_id} --workspace {self.workspace} "
                "--execute --confirm LOCAL_AGENT_EXECUTION"
            )
        elif self.gate.decision == "approval_required":
            actions.append("Record human approval before live action.")
            if self.ledger:
                actions.append(
                    f"delegation approval-decision --ledger {self.ledger} --action-id {self.action_id} "
                    "--decision approve --approver YOUR_NAME"
                )
        elif self.gate.decision == "block":
            actions.append(self.gate.next_action)
        else:
            actions.append("Review warnings before execution or promotion.")
        actions.append("Keep recorder/evidence attached to this action.")
        return tuple(_dedupe(actions))

    @property
    def safe_next_step(self) -> str:
        if self.expired:
            return "Regenerate the approval preview before approving or executing this request."
        if self.gate.decision == "allow":
            return "Run under DelegationHQ control with the exact execution confirmation token."
        if self.gate.decision == "approval_required":
            return "Record a human approve/block decision before live action."
        if self.gate.decision == "block":
            return "Change the request, passport, target, or risk before trying again."
        return "Review the warning and request more evidence before increasing autonomy."

    @property
    def decision_commands(self) -> tuple[JsonMap, ...]:
        commands: list[JsonMap] = []
        if self.gate.decision == "approval_required" and self.ledger:
            commands.extend(
                [
                    {
                        "id": "approve",
                        "label": "Approve",
                        "command": (
                            f"delegation approval-decision --ledger {self.ledger} --action-id {self.action_id} "
                            "--decision approve --approver YOUR_NAME"
                        ),
                        "writes_ledger": True,
                    },
                    {
                        "id": "block",
                        "label": "Block",
                        "command": (
                            f"delegation approval-decision --ledger {self.ledger} --action-id {self.action_id} "
                            "--decision block --approver YOUR_NAME"
                        ),
                        "writes_ledger": True,
                    },
                ]
            )
        if self.gate.decision == "allow" and self.workspace:
            commands.append(
                {
                    "id": "execute",
                    "label": "Execute",
                    "command": (
                        f"delegation agent-run {self.agent_id} --workspace {self.workspace} --action {self.action} "
                        f"--target {self.target} --execute --confirm LOCAL_AGENT_EXECUTION"
                    ),
                    "writes_ledger": True,
                }
            )
        return tuple(commands)

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": APPROVAL_PREVIEW_SCHEMA_VERSION,
            "status": self.status,
            "workspace": self.workspace,
            "ledger": self.ledger,
            "agent_id": self.agent_id,
            "action": self.action,
            "target": self.target,
            "action_id": self.action_id,
            "decision": self.gate.decision,
            "risk": self.gate.effective_risk,
            "summary": self.summary,
            "can_execute": self.can_execute,
            "command": self.command,
            "reviewer_note": self.reviewer_note,
            "expires_at": self.expires_at,
            "expired": self.expired,
            "request_context": self.request_context or {},
            "resource_summary": self.resource_summary or {},
            "evidence_status": self.evidence_status or {},
            "history": self.history or {},
            "safe_next_step": self.safe_next_step,
            "decision_commands": list(self.decision_commands),
            "required_approvals": list(self.required_approvals),
            "missing_approvals": list(self.missing_approvals),
            "required_evidence": list(self.gate.required_evidence),
            "missing_evidence": list(self.gate.missing_evidence),
            "provided_approvals": list(self.gate.provided_approvals),
            "provided_evidence": list(self.gate.provided_evidence),
            "gate": self.gate.to_dict(),
            "warnings": list(self.warnings),
            "next_actions": list(self.next_actions),
        }


def build_approval_preview_report(
    *,
    agent_id: str,
    action: str = "read.workspace",
    target: str = "workspace",
    workspace_root: Path | None = None,
    harnessfile: Path | None = None,
    registry_paths: T.Sequence[Path] = (),
    ledger_path: Path | None = None,
    requested_risk: str | None = None,
    approvals: T.Sequence[str] = (),
    evidence: T.Sequence[str] = (),
    reviewer_note: str | None = None,
    expires_at: str | None = None,
) -> ApprovalPreviewReport:
    """Build the app-ready human card for an agent request."""

    warnings: list[str] = []
    resolved_workspace = workspace_root.resolve() if workspace_root else None
    resolved_harnessfile = harnessfile
    resolved_registries = list(registry_paths)
    resolved_ledger = ledger_path

    if resolved_workspace is not None:
        workspace_harnessfile = resolved_workspace / DEFAULT_WORKSPACE_HARNESS
        workspace_registry = resolved_workspace / DEFAULT_WORKSPACE_REGISTRY
        if resolved_harnessfile is None and workspace_harnessfile.exists():
            resolved_harnessfile = workspace_harnessfile
        if not resolved_registries and workspace_registry.exists():
            resolved_registries.append(workspace_registry)
        if resolved_ledger is None:
            resolved_ledger = resolved_workspace / DEFAULT_WORKSPACE_AGENT_RUN_LEDGER

    manifest = None
    if resolved_harnessfile is not None:
        manifest, manifest_warnings = _load_optional_manifest(resolved_harnessfile)
        warnings.extend(manifest_warnings)

    gate = build_agent_gate_report(
        agent_id=agent_id,
        action=action,
        target=target,
        manifest=manifest,
        manifest_source=str(resolved_harnessfile) if resolved_harnessfile else None,
        registry_paths=tuple(resolved_registries),
        requested_risk=requested_risk,
        provided_approvals=approvals,
        provided_evidence=evidence,
    )
    command = _command_from_gate(gate)
    action_id = _action_id(agent_id, gate.action)
    expired, expiration_warning = _expiration_state(expires_at)
    history = _approval_history(resolved_ledger, action_id)
    if expiration_warning:
        warnings.append(expiration_warning)
    return ApprovalPreviewReport(
        status=gate.status,
        workspace=str(resolved_workspace) if resolved_workspace else None,
        ledger=str(resolved_ledger) if resolved_ledger else None,
        agent_id=agent_id,
        action=gate.action,
        target=gate.target,
        gate=gate,
        summary=_summary(gate),
        can_execute=gate.decision == "allow" and not expired,
        command=command,
        reviewer_note=_clean_optional(reviewer_note),
        expires_at=_clean_optional(expires_at),
        expired=expired,
        request_context=_request_context(
            gate,
            reviewer_note=reviewer_note,
            expires_at=expires_at,
            expired=expired,
        ),
        resource_summary=_resource_summary(gate),
        evidence_status=_evidence_status(gate),
        history=history,
        warnings=tuple([*warnings, *gate.registry_warnings]),
    )


def render_approval_preview_report(report: ApprovalPreviewReport) -> str:
    lines = [
        "Agent Approval Preview",
        "",
        f"Status: {report.status}",
        f"Decision: {report.gate.decision}",
        f"Agent: {report.agent_id}",
        f"Action: {report.action}",
        f"Target: {report.target}",
        f"Risk: {report.gate.effective_risk}",
        f"Can execute now: {str(report.can_execute).lower()}",
    ]
    if report.workspace:
        lines.append(f"Workspace: {report.workspace}")
    if report.ledger:
        lines.append(f"Ledger: {report.ledger}")
    if report.command:
        lines.append(f"Command: {report.command}")

    lines.extend(["", "Request packet:"])
    context = report.request_context or {}
    lines.append(f"- intent: {context.get('intent', 'unknown')}")
    lines.append(f"- operation: {context.get('operation', 'unknown')}")
    lines.append(f"- decision reason: {context.get('decision_reason', 'unknown')}")
    if report.reviewer_note:
        lines.append(f"- reviewer note: {report.reviewer_note}")
    if report.expires_at:
        lines.append(f"- expires: {report.expires_at} ({'expired' if report.expired else 'active'})")

    resource = report.resource_summary or {}
    lines.extend(["", "Resources:"])
    lines.append(f"- requested target: {resource.get('target', report.target)}")
    lines.append(f"- target kind: {resource.get('target_kind', 'unknown')}")
    if resource.get("endpoint"):
        lines.append(f"- endpoint: {resource['endpoint']}")
    for item in resource.get("touches", []) if isinstance(resource.get("touches"), list) else []:
        lines.append(f"- touches: {item}")

    lines.extend(["", "Plain language:", f"- {report.summary}"])
    lines.append(f"- Safe next step: {report.safe_next_step}")
    if report.gate.passport:
        lines.append(f"- Runtime: {report.gate.passport.runtime_type}; autonomy: {report.gate.passport.autonomy_level}.")

    lines.extend(["", "Approvals:"])
    if report.required_approvals:
        lines.extend(f"- required: {item}" for item in report.required_approvals)
    else:
        lines.append("- required: none")
    if report.missing_approvals:
        lines.extend(f"- missing: {item}" for item in report.missing_approvals)

    lines.extend(["", "Evidence:"])
    if report.gate.required_evidence:
        lines.extend(f"- required: {item}" for item in report.gate.required_evidence)
    else:
        lines.append("- required: none")
    if report.gate.missing_evidence:
        lines.extend(f"- not yet present: {item}" for item in report.gate.missing_evidence)
    evidence_status = report.evidence_status or {}
    if evidence_status:
        lines.append(f"- status: {evidence_status.get('status', 'unknown')}")

    history = report.history or {}
    lines.extend(["", "History:"])
    lines.append(f"- status: {history.get('status', 'unknown')}")
    lines.append(f"- summary: {history.get('summary', 'No history loaded.')}")
    if history.get("matching_event_count") is not None:
        lines.append(f"- matching events: {history.get('matching_event_count')}")
    if history.get("gate_count") is not None:
        lines.append(f"- previous gate receipts: {history.get('gate_count')}")
    recent = history.get("recent_events") if isinstance(history.get("recent_events"), list) else []
    for item in recent[-3:]:
        if isinstance(item, dict):
            lines.append(
                f"- recent: {item.get('sequence', '?')}. {item.get('event_type', 'event')} [{item.get('status', 'unknown')}]"
            )

    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)

    if report.decision_commands:
        lines.extend(["", "Decision commands:"])
        for command in report.decision_commands:
            lines.append(f"- {command['label']}: {command['command']}")

    lines.extend(["", "Next:"])
    lines.extend(f"- {action}" for action in report.next_actions)
    return "\n".join(lines)


def _load_optional_manifest(path: Path) -> tuple[Manifest | None, list[str]]:
    try:
        manifest = load_manifest(path)
    except (OSError, ManifestError) as exc:
        return None, [f"Harnessfile could not be loaded: {exc}"]
    errors = validate_manifest(manifest)
    if errors:
        return None, [f"Harnessfile is invalid: {error}" for error in errors]
    return manifest, []


def _summary(gate: AgentGateReport) -> str:
    if gate.decision == "allow":
        return "This agent request is inside its passport and can run after explicit execution confirmation."
    if gate.decision == "approval_required":
        return "This agent request is allowed by scope, but a human must approve before live action."
    if gate.decision == "block":
        return "This agent request is blocked before execution because identity, scope, risk, or policy failed."
    return "This agent request is possible, but warnings should be reviewed before execution."


def _request_context(
    gate: AgentGateReport,
    *,
    reviewer_note: str | None,
    expires_at: str | None,
    expired: bool,
) -> JsonMap:
    operation = _operation(gate.action)
    return {
        "agent_id": gate.agent_id,
        "action": gate.action,
        "target": gate.target,
        "operation": operation,
        "intent": f"{gate.agent_id} wants to {operation} {gate.target}",
        "decision": gate.decision,
        "risk": gate.effective_risk,
        "reviewer_note": _clean_optional(reviewer_note),
        "expires_at": _clean_optional(expires_at),
        "expired": expired,
        "decision_reason": _decision_reason(gate),
    }


def _resource_summary(gate: AgentGateReport) -> JsonMap:
    passport = gate.passport
    touches = [gate.target]
    endpoint = ""
    if passport:
        endpoint = _endpoint_summary(passport.endpoint)
        touches.extend(passport.allowed_data)
        touches.extend(f"tool:{item}" for item in passport.allowed_tools)
        touches.extend(f"output:{item}" for item in passport.expected_outputs)
    return {
        "target": gate.target,
        "target_kind": _target_kind(gate.target),
        "operation": _operation(gate.action),
        "runtime_type": passport.runtime_type if passport else "unknown",
        "endpoint": endpoint,
        "touches": _dedupe(touches),
        "allowed_data": list(passport.allowed_data) if passport else [],
        "allowed_tools": list(passport.allowed_tools) if passport else [],
        "expected_outputs": list(passport.expected_outputs) if passport else [],
        "matched_action_check": _check_message(gate, "scope.action"),
        "matched_target_check": _check_message(gate, "scope.target"),
    }


def _evidence_status(gate: AgentGateReport) -> JsonMap:
    if not gate.required_evidence:
        status = "not_declared"
    elif gate.missing_evidence:
        status = "missing"
    else:
        status = "complete"
    return {
        "status": status,
        "required": list(gate.required_evidence),
        "provided": list(gate.provided_evidence),
        "missing": list(gate.missing_evidence),
        "summary": _evidence_summary(status, gate),
    }


def _approval_history(ledger_path: Path | None, action_id: str) -> JsonMap:
    if ledger_path is None:
        return _history_payload("not_available", None, (), "No ledger was provided for history.")
    if not ledger_path.exists():
        return _history_payload("no_history", str(ledger_path), (), "No prior ledger history exists for this request.")
    try:
        events = load_ledger_events(ledger_path)
    except LedgerError as exc:
        return _history_payload("error", str(ledger_path), (), f"Ledger history could not be read: {exc}")
    matching = tuple(event for event in events if _event_matches_action(event, action_id))
    if not matching:
        return _history_payload("new_request", str(ledger_path), matching, "No previous events match this agent action.")
    return _history_payload("has_history", str(ledger_path), matching, _history_summary(matching))


def _history_payload(status: str, ledger: str | None, events: T.Sequence[JsonMap], summary: str) -> JsonMap:
    gate_count = sum(1 for event in events if _event_type(event) == "agent.gate.previewed")
    approval_count = sum(1 for event in events if _event_type(event) == "approval.granted")
    block_count = sum(1 for event in events if _event_type(event) == "approval.denied")
    recorded_count = sum(1 for event in events if _event_type(event).startswith("runprint.recording."))
    failed_count = sum(1 for event in events if _event_status(event) in {"failed", "blocked", "timed_out"})
    latest = events[-1] if events else {}
    return {
        "status": status,
        "ledger": ledger,
        "summary": summary,
        "matching_event_count": len(events),
        "gate_count": gate_count,
        "approval_count": approval_count,
        "block_count": block_count,
        "recorded_count": recorded_count,
        "failed_count": failed_count,
        "latest_sequence": _event_sequence(latest),
        "latest_event_type": _event_type(latest) if latest else None,
        "latest_status": _event_status(latest) if latest else None,
        "recent_events": [_history_event(event) for event in events[-5:]],
    }


def _history_event(event: JsonMap) -> JsonMap:
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    return {
        "sequence": _event_sequence(event),
        "timestamp": _clean_optional(event.get("timestamp")),
        "event_type": _event_type(event),
        "status": _event_status(event),
        "message": _clean_optional(event.get("message")),
        "decision": _clean_optional(details.get("decision")),
        "approver": _clean_optional(details.get("approver")),
    }


def _history_summary(events: T.Sequence[JsonMap]) -> str:
    gate_count = sum(1 for event in events if _event_type(event) == "agent.gate.previewed")
    recorded_count = sum(1 for event in events if _event_type(event).startswith("runprint.recording."))
    approval_count = sum(1 for event in events if _event_type(event) == "approval.granted")
    block_count = sum(1 for event in events if _event_type(event) == "approval.denied")
    parts = [f"{len(events)} matching event(s)", f"{gate_count} gate receipt(s)"]
    if recorded_count:
        parts.append(f"{recorded_count} recorded proof event(s)")
    if approval_count:
        parts.append(f"{approval_count} approval(s)")
    if block_count:
        parts.append(f"{block_count} block(s)")
    return "; ".join(parts) + "."


def _event_matches_action(event: JsonMap, action_id: str) -> bool:
    if event.get("action_id") == action_id:
        return True
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    for key in ("target_action_id", "gate_action_id"):
        if details.get(key) == action_id:
            return True
    return False


def _command_from_gate(gate: AgentGateReport) -> str | None:
    if not gate.passport:
        return None
    endpoint = gate.passport.endpoint
    if endpoint.get("type") != "command":
        return None
    value = endpoint.get("value")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _expiration_state(expires_at: str | None) -> tuple[bool, str | None]:
    value = _clean_optional(expires_at)
    if not value:
        return False, None
    parsed = _parse_datetime(value)
    if parsed is None:
        return False, "Approval preview expiration could not be parsed; use an ISO timestamp."
    expired = parsed <= datetime.now(timezone.utc)
    if expired:
        return True, "Approval preview is expired. Regenerate before approving or executing."
    return False, None


def _parse_datetime(value: str) -> datetime | None:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _decision_reason(gate: AgentGateReport) -> str:
    for status in ("blocked", "approval_required", "warning"):
        for check in gate.checks:
            if check.status == status:
                return check.message
    for check in gate.checks:
        if check.id in {"scope.action", "scope.target", "approval.required"}:
            continue
    return gate.next_action


def _check_message(gate: AgentGateReport, check_id: str) -> str | None:
    for check in gate.checks:
        if check.id == check_id:
            return check.message
    return None


def _evidence_summary(status: str, gate: AgentGateReport) -> str:
    if status == "complete":
        return "All required evidence is already present."
    if status == "missing":
        return "Required evidence still needs to be recorded: " + ", ".join(gate.missing_evidence) + "."
    return "No evidence requirement was declared, so trust cannot be earned cleanly."


def _endpoint_summary(value: JsonMap) -> str:
    endpoint_type = value.get("type", "unknown")
    endpoint_value = value.get("value", "")
    if endpoint_value:
        return f"{endpoint_type}: {endpoint_value}"
    return str(endpoint_type)


def _target_kind(value: str) -> str:
    lowered = value.lower()
    if any(item in lowered for item in ("file", ".py", ".md", ".json", ".yaml", ".yml")):
        return "file"
    if any(item in lowered for item in ("github", "issue", "pull_request", "workflow")):
        return "github"
    if any(item in lowered for item in ("crm", "customer", "contact")):
        return "business-data"
    if any(item in lowered for item in ("workspace", "repo", "repository")):
        return "workspace"
    if "mcp" in lowered or "tool" in lowered:
        return "tool"
    return "resource"


def _operation(action: str) -> str:
    return action.split(".", 1)[0].strip() or action


def _action_id(agent_id: str, action: str) -> str:
    return f"agent_gate.{_event_id_part(agent_id)}.{_event_id_part(action)}"


def _event_id_part(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    return "_".join(part for part in cleaned.split("_") if part) or "unknown"


def _event_type(event: JsonMap) -> str:
    value = event.get("type")
    return value if isinstance(value, str) and value.strip() else ""


def _event_status(event: JsonMap) -> str:
    value = event.get("status")
    return value if isinstance(value, str) and value.strip() else ""


def _event_sequence(event: JsonMap) -> int | None:
    value = event.get("sequence")
    return value if isinstance(value, int) else None


def _clean_optional(value: T.Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _dedupe(values: T.Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
