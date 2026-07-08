#!/usr/bin/env python3
"""Action request intake for the DelegationHQ trust cockpit."""

from __future__ import annotations

import hashlib
import typing as T
from dataclasses import dataclass
from datetime import datetime, timezone

from delegation_bot.agent_gate import AgentGateReport, build_agent_gate_events, build_agent_gate_report
from delegation_bot.harness_manifest import Manifest
from delegation_bot.harness_plan import LedgerEvent


JsonMap = dict[str, T.Any]
ACTION_REQUEST_SCHEMA_VERSION = "delegation.action-request.v1"


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
