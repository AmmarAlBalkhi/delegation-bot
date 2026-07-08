#!/usr/bin/env python3
"""Action request intake for the DelegationHQ trust cockpit."""

from __future__ import annotations

import hashlib
import typing as T
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from delegation_bot.agent_gate import AgentGateReport, build_agent_gate_events, build_agent_gate_report
from delegation_bot.agent_run import (
    LOCAL_AGENT_EXECUTION_CONFIRMATION,
    AgentRunReport,
    run_agent_under_control,
)
from delegation_bot.approval_inbox import ApprovalInboxItem, build_approval_inbox_report
from delegation_bot.harness_manifest import Manifest
from delegation_bot.harness_plan import LedgerEvent


JsonMap = dict[str, T.Any]
ACTION_REQUEST_SCHEMA_VERSION = "delegation.action-request.v1"
REQUEST_STATUS_SCHEMA_VERSION = "delegation.request-status.v1"
REQUEST_RUN_SCHEMA_VERSION = "delegation.request-run.v1"


@dataclass(frozen=True)
class ActionRequestReport:
    schema_version: str
    status: str
    ledger_source: str
    action_id: str
    request_id: str
    requested_by: str
    agent_id: str
    action: str
    target: str
    summary: str
    gate: AgentGateReport
    wrote_ledger: bool
    next_action: str

    @property
    def blocked(self) -> bool:
        return self.gate.blocked

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "ledger_source": self.ledger_source,
            "action_id": self.action_id,
            "request_id": self.request_id,
            "requested_by": self.requested_by,
            "agent_id": self.agent_id,
            "action": self.action,
            "target": self.target,
            "summary": self.summary,
            "gate": self.gate.to_dict(),
            "wrote_ledger": self.wrote_ledger,
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class RequestStatusReport:
    schema_version: str
    status: str
    ledger_source: str
    action_id: str | None
    item: ApprovalInboxItem | None
    next_action: str
    warnings: tuple[str, ...] = ()

    @property
    def ready_to_run(self) -> bool:
        return self.status in {"approved", "needs_evidence", "ready_for_recording"}

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "ledger_source": self.ledger_source,
            "action_id": self.action_id,
            "item": self.item.to_dict() if self.item else None,
            "ready_to_run": self.ready_to_run,
            "warnings": list(self.warnings),
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class RequestRunReport:
    schema_version: str
    status: str
    ledger_source: str
    action_id: str | None
    request_status: RequestStatusReport
    agent_run: AgentRunReport | None
    message: str
    next_action: str

    @property
    def blocked(self) -> bool:
        return self.agent_run.blocked if self.agent_run else self.status != "recorded"

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "ledger_source": self.ledger_source,
            "action_id": self.action_id,
            "request_status": self.request_status.to_dict(),
            "agent_run": self.agent_run.to_dict() if self.agent_run else None,
            "message": self.message,
            "next_action": self.next_action,
        }


def build_action_request_report(
    *,
    agent_id: str,
    action: str,
    target: str,
    ledger_source: str,
    manifest: Manifest | None = None,
    manifest_source: str | None = None,
    registry_paths: T.Sequence[T.Any] = (),
    requested_risk: str | None = None,
    provided_evidence: T.Sequence[str] = (),
    provided_approvals: T.Sequence[str] = (),
    requested_by: str | None = None,
    summary: str | None = None,
    wrote_ledger: bool = False,
) -> ActionRequestReport:
    gate = build_agent_gate_report(
        agent_id=agent_id,
        action=action,
        target=target,
        manifest=manifest,
        manifest_source=manifest_source,
        registry_paths=registry_paths,
        requested_risk=requested_risk,
        provided_evidence=provided_evidence,
        provided_approvals=provided_approvals,
    )
    action_id = _action_id(gate.agent_id, gate.action)
    clean_requested_by = _string(requested_by, default=gate.agent_id)
    clean_summary = _string(summary, default=f"{gate.agent_id} requests `{gate.action}` on `{gate.target}`.")
    status = _status(gate.decision)
    return ActionRequestReport(
        schema_version=ACTION_REQUEST_SCHEMA_VERSION,
        status=status,
        ledger_source=ledger_source,
        action_id=action_id,
        request_id=_request_id(action_id, clean_requested_by, clean_summary),
        requested_by=clean_requested_by,
        agent_id=gate.agent_id,
        action=gate.action,
        target=gate.target,
        summary=clean_summary,
        gate=gate,
        wrote_ledger=wrote_ledger,
        next_action=_next_action(gate.decision, action_id),
    )


def build_action_request_events(
    report: ActionRequestReport,
    *,
    run_id: str,
    start_sequence: int,
    timestamp: str | None = None,
) -> list[LedgerEvent]:
    event_time = timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    gate_events = build_agent_gate_events(
        report.gate,
        run_id=run_id,
        start_sequence=start_sequence + 1,
        timestamp=event_time,
    )
    gate_action_id = gate_events[0].action_id or report.action_id
    request_event = LedgerEvent(
        run_id=run_id,
        sequence=start_sequence,
        timestamp=event_time,
        type="action.requested",
        status=report.status,
        message=f"{report.agent_id} requested `{report.action}` on `{report.target}`.",
        action_id=gate_action_id,
        details={
            "schema_version": ACTION_REQUEST_SCHEMA_VERSION,
            "adapter": "delegation.action_request",
            "request_id": report.request_id,
            "requested_by": report.requested_by,
            "agent_id": report.agent_id,
            "requested_action": report.action,
            "target": report.target,
            "summary": report.summary,
            "gate_decision": report.gate.decision,
            "effective_risk": report.gate.effective_risk,
            "dry_run": True,
        },
    )
    return [request_event, *gate_events]


def build_request_status_report(
    ledger_events: T.Sequence[JsonMap],
    *,
    ledger_source: str = "<memory>",
    action_id: str | None = None,
) -> RequestStatusReport:
    inbox = build_approval_inbox_report(ledger_events, ledger_source=ledger_source)
    item = _select_inbox_item(inbox.items, action_id=action_id)
    if item is None:
        clean_action_id = _string(action_id) or None
        return RequestStatusReport(
            schema_version=REQUEST_STATUS_SCHEMA_VERSION,
            status="missing",
            ledger_source=ledger_source,
            action_id=clean_action_id,
            item=None,
            next_action="Submit an action request with `delegation action-request AGENT --workspace . --action ACTION --target TARGET`.",
            warnings=(f"No request card found for `{clean_action_id}`.",) if clean_action_id else ("No request cards found.",),
        )
    return RequestStatusReport(
        schema_version=REQUEST_STATUS_SCHEMA_VERSION,
        status=item.status,
        ledger_source=ledger_source,
        action_id=item.action_id,
        item=item,
        next_action=_status_next_action(item, ledger_source=ledger_source),
        warnings=(),
    )


def run_request_under_control(
    ledger_events: T.Sequence[JsonMap],
    *,
    ledger_path: Path,
    action_id: str | None = None,
    registry_paths: T.Sequence[Path] = (),
    manifest: Manifest | None = None,
    manifest_source: str | None = None,
    requested_risk: str | None = None,
    confirm: str | None = None,
    cwd: Path | None = None,
    output_dir: Path | None = None,
    timeout_seconds: int = 60,
) -> RequestRunReport:
    status = build_request_status_report(ledger_events, ledger_source=str(ledger_path), action_id=action_id)
    item = status.item
    if item is None:
        return _request_run_refused(status, "No request card was found.")
    if item.status in {"pending_approval", "warning"}:
        return _request_run_refused(status, "Request needs a human decision before execution.")
    if item.status in {"blocked_by_human", "blocked_by_gate"}:
        return _request_run_refused(status, "Request is blocked.")
    if item.status == "recorded":
        return _request_run_refused(status, "Request already has recorded execution evidence.")
    if item.status not in {"approved", "needs_evidence", "ready_for_recording"}:
        return _request_run_refused(status, f"Request is `{item.status}` and is not ready to run.")
    if confirm != LOCAL_AGENT_EXECUTION_CONFIRMATION:
        return _request_run_refused(
            status,
            f"Request execution requires --confirm {LOCAL_AGENT_EXECUTION_CONFIRMATION}.",
        )
    approvals = item.required_approvals if item.status == "approved" else ()
    agent_run = run_agent_under_control(
        agent_id=item.agent_id,
        action=item.action,
        target=item.target,
        ledger_path=ledger_path,
        registry_paths=registry_paths,
        manifest=manifest,
        manifest_source=manifest_source,
        requested_risk=requested_risk,
        approvals=approvals,
        evidence=(),
        execute=True,
        confirm=confirm,
        cwd=cwd,
        output_dir=output_dir,
        timeout_seconds=timeout_seconds,
    )
    return RequestRunReport(
        schema_version=REQUEST_RUN_SCHEMA_VERSION,
        status=agent_run.status,
        ledger_source=str(ledger_path),
        action_id=item.action_id,
        request_status=status,
        agent_run=agent_run,
        message="Request ran under DelegationHQ control." if not agent_run.blocked else "Request did not execute.",
        next_action=agent_run.next_actions[0] if agent_run.next_actions else "Review the mission timeline.",
    )


def render_action_request_report(report: ActionRequestReport) -> str:
    lines = [
        "Action Request",
        "",
        f"Status: {report.status}",
        f"Ledger: {report.ledger_source}",
        f"Request: {report.request_id}",
        f"Action: {report.action_id}",
        f"Agent: {report.agent_id}",
        f"Wants: {report.action} on {report.target}",
        f"Risk: {report.gate.effective_risk}",
        f"Gate: {report.gate.decision}",
        f"Ledger written: {str(report.wrote_ledger).lower()}",
        "",
        "Plain language:",
        "- The agent asked for permission.",
        "- DelegationHQ checked the Agent Passport before anything ran.",
        "- This is a local control receipt, not live execution.",
        "",
        "Next:",
        f"- {report.next_action}",
    ]
    if report.gate.required_evidence:
        lines.extend(["", "Evidence needed:", "- " + ", ".join(report.gate.required_evidence)])
    if report.gate.matched_approvals:
        lines.extend(["", "Approval needed:", "- " + ", ".join(report.gate.matched_approvals)])
    return "\n".join(lines)


def render_request_status_report(report: RequestStatusReport) -> str:
    lines = [
        "Request Status",
        "",
        f"Status: {report.status}",
        f"Ledger: {report.ledger_source}",
        f"Action: {report.action_id or 'none'}",
        f"Ready to run: {str(report.ready_to_run).lower()}",
    ]
    if report.item:
        item = report.item
        lines.extend(
            [
                f"Agent: {item.agent_id}",
                f"Wants: {item.action} on {item.target}",
                f"Risk: {item.risk}",
                f"Gate: {item.gate_decision}",
                f"Evidence: {item.evidence_status}",
            ]
        )
        if item.request_summary:
            lines.append(f"Summary: {item.request_summary}")
        if item.latest_decision:
            lines.append(f"Decision: {item.latest_decision.decision} by {item.latest_decision.approver}")
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend(
        [
            "",
            "Plain language:",
            "- This is where the request is in the trust loop.",
            "- Run only when the status is approved, needs_evidence, or ready_for_recording.",
            "",
            "Next:",
            f"- {report.next_action}",
        ]
    )
    return "\n".join(lines)


def render_request_run_report(report: RequestRunReport) -> str:
    lines = [
        "Request Run",
        "",
        f"Status: {report.status}",
        f"Ledger: {report.ledger_source}",
        f"Action: {report.action_id or 'none'}",
        report.message,
    ]
    if report.agent_run:
        lines.extend(
            [
                "",
                f"Agent: {report.agent_run.agent_id}",
                f"Executed: {str(report.agent_run.executed).lower()}",
                f"Gate: {report.agent_run.gate.decision}",
            ]
        )
        if report.agent_run.output_artifact:
            lines.append(f"Evidence: {report.agent_run.output_artifact}")
        if report.agent_run.stdout_tail:
            lines.extend(["", "Stdout:", report.agent_run.stdout_tail])
        if report.agent_run.stderr_tail:
            lines.extend(["", "Stderr:", report.agent_run.stderr_tail])
    lines.extend(
        [
            "",
            "Plain language:",
            "- DelegationHQ moved a cleared request into controlled execution.",
            "- Pending, blocked, and already-recorded requests are refused.",
            "",
            "Next:",
            f"- {report.next_action}",
        ]
    )
    return "\n".join(lines)


def _status(decision: str) -> str:
    if decision == "block":
        return "blocked"
    if decision == "approval_required":
        return "pending_approval"
    if decision == "warn":
        return "needs_review"
    return "ready_for_recording"


def _next_action(decision: str, action_id: str) -> str:
    if decision == "approval_required":
        return f"Review the approval card, then run `delegation approval-decision --ledger LEDGER --action-id {action_id} --decision approve|block --approver NAME`."
    if decision == "block":
        return "Change the request, target, or Agent Passport before trying again."
    if decision == "warn":
        return "Review the warning, then attach evidence before increasing trust."
    return "Execute under recorder control, then attach evidence and run evals."


def _select_inbox_item(items: T.Sequence[ApprovalInboxItem], *, action_id: str | None) -> ApprovalInboxItem | None:
    clean_action_id = _string(action_id)
    if clean_action_id:
        for item in reversed(items):
            if item.action_id == clean_action_id:
                return item
        return None
    return items[-1] if items else None


def _status_next_action(item: ApprovalInboxItem, *, ledger_source: str) -> str:
    if item.status == "pending_approval":
        return f"delegation approval-decision --ledger {ledger_source} --action-id {item.action_id} --decision approve --approver NAME"
    if item.status == "approved":
        return f"delegation request-run --ledger {ledger_source} --action-id {item.action_id} --confirm {LOCAL_AGENT_EXECUTION_CONFIRMATION}"
    if item.status == "needs_evidence":
        return f"delegation request-run --ledger {ledger_source} --action-id {item.action_id} --confirm {LOCAL_AGENT_EXECUTION_CONFIRMATION}"
    if item.status == "ready_for_recording":
        return f"delegation request-run --ledger {ledger_source} --action-id {item.action_id} --confirm {LOCAL_AGENT_EXECUTION_CONFIRMATION}"
    if item.status in {"blocked_by_human", "blocked_by_gate"}:
        return "Change the request, passport, target, or approval decision before retrying."
    if item.status == "recorded":
        return f"delegation mission-status --ledger {ledger_source}"
    return item.next_action


def _request_run_refused(status: RequestStatusReport, message: str) -> RequestRunReport:
    return RequestRunReport(
        schema_version=REQUEST_RUN_SCHEMA_VERSION,
        status=status.status,
        ledger_source=status.ledger_source,
        action_id=status.action_id,
        request_status=status,
        agent_run=None,
        message=message,
        next_action=status.next_action,
    )


def _action_id(agent_id: str, action: str) -> str:
    return f"agent_gate.{_event_id_part(agent_id)}.{_event_id_part(action)}"


def _request_id(action_id: str, requested_by: str, summary: str) -> str:
    raw = f"{action_id}|{requested_by}|{summary}".encode("utf-8")
    return "action_request_" + hashlib.sha256(raw).hexdigest()[:20]


def _event_id_part(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    return "_".join(part for part in cleaned.split("_") if part) or "unknown"


def _string(value: T.Any, *, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
