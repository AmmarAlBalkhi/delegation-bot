#!/usr/bin/env python3
"""Plain mission status over a DelegationHQ run ledger."""

from __future__ import annotations

import typing as T
from dataclasses import dataclass

from delegation_bot.agent_gate import build_agent_gate_audit_report
from delegation_bot.approval_inbox import build_approval_inbox_report
from delegation_bot.dashboard import build_dashboard_snapshot
from delegation_bot.evidence_report import build_evidence_report


JsonMap = dict[str, T.Any]
MISSION_STATUS_SCHEMA_VERSION = "delegation.mission-status.v1"


@dataclass(frozen=True)
class MissionStatusReport:
    schema_version: str
    status: str
    ledger_source: str
    event_count: int
    mission: JsonMap
    control_loop: JsonMap
    proof: tuple[str, ...]
    attention: tuple[str, ...]
    next_actions: tuple[str, ...]

    @property
    def blocked(self) -> bool:
        return self.status in {"blocked", "needs_attention"}

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "ledger_source": self.ledger_source,
            "event_count": self.event_count,
            "mission": self.mission,
            "control_loop": self.control_loop,
            "proof": list(self.proof),
            "attention": list(self.attention),
            "next_actions": list(self.next_actions),
        }


def build_mission_status_report(
    ledger_events: T.Sequence[JsonMap],
    *,
    ledger_source: str = "<memory>",
) -> MissionStatusReport:
    dashboard = build_dashboard_snapshot(ledger_events, source=ledger_source)
    evidence = build_evidence_report(ledger_events, source=ledger_source)
    audit = build_agent_gate_audit_report(ledger_events, ledger_source=ledger_source)
    inbox = build_approval_inbox_report(ledger_events, ledger_source=ledger_source)

    primary_action_id = _primary_action_id(inbox.to_dict())
    control_loop = {
        "dashboard_status": dashboard.status,
        "agent_audit_status": audit.status,
        "approval_inbox_status": inbox.status,
        "gate_previews": audit.gate_count,
        "runprint_planned_bundles": audit.runprint_bundle_count,
        "runprint_recorded_events": audit.recorded_event_count,
        "approval_cards": inbox.item_count,
        "pending_approval": inbox.pending_count,
        "approved": inbox.approved_count,
        "blocked": inbox.blocked_count,
        "needs_evidence": inbox.needs_evidence_count,
        "primary_action_id": primary_action_id,
    }
    status = _mission_status(
        dashboard_status=dashboard.status,
        audit_status=audit.status,
        inbox_status=inbox.status,
        has_gate=bool(audit.gate_count),
    )
    return MissionStatusReport(
        schema_version=MISSION_STATUS_SCHEMA_VERSION,
        status=status,
        ledger_source=ledger_source,
        event_count=len(ledger_events),
        mission=_mission(dashboard.to_dict()),
        control_loop=control_loop,
        proof=tuple(_proof_lines(evidence.to_dict(), audit.to_dict())),
        attention=tuple(_attention_lines(inbox.to_dict(), audit.to_dict())),
        next_actions=tuple(_next_actions(status, ledger_source, primary_action_id)),
    )


def render_mission_status_report(report: MissionStatusReport) -> str:
    mission_id = report.mission.get("id") or "unknown"
    objective = report.mission.get("objective") or "unknown"
    control = report.control_loop
    lines = [
        "DelegationHQ Mission Status",
        "",
        f"Status: {report.status}",
        f"Ledger: {report.ledger_source}",
        f"Events: {report.event_count}",
        "",
        "Mission:",
        f"- id: {mission_id}",
        f"- objective: {objective}",
        "",
        "Control loop:",
        f"- gate receipts: {control.get('gate_previews', 0)}",
        f"- approval cards: {control.get('approval_cards', 0)} total, {control.get('pending_approval', 0)} pending",
        f"- RunPrint: {control.get('runprint_recorded_events', 0)} recorded, {control.get('runprint_planned_bundles', 0)} planned",
        f"- audit: {control.get('agent_audit_status', 'unknown')}",
    ]
    if control.get("primary_action_id"):
        lines.append(f"- primary action: {control['primary_action_id']}")

    lines.extend(["", "Plain language:"])
    lines.extend(f"- {line}" for line in _plain_language(report))

    lines.extend(["", "Proof:"])
    lines.extend(f"- {line}" for line in (report.proof or ("No proof has been recorded yet.",)))

    lines.extend(["", "Needs attention:"])
    lines.extend(f"- {line}" for line in (report.attention or ("none",)))

    lines.extend(["", "Next:"])
    lines.extend(f"- {action}" for action in report.next_actions)
    return "\n".join(lines)


def _mission_status(
    *,
    dashboard_status: str,
    audit_status: str,
    inbox_status: str,
    has_gate: bool,
) -> str:
    if inbox_status == "blocked" or audit_status == "blocked":
        return "blocked"
    if inbox_status == "needs_attention" or audit_status in {"approval_required", "needs_evidence", "warning"}:
        return "needs_attention"
    if audit_status == "recorded":
        return "recorded"
    if audit_status == "ready_for_recording":
        return "ready_for_recording"
    if not has_gate:
        return "planned" if dashboard_status == "ready" else dashboard_status
    return dashboard_status


def _mission(dashboard: JsonMap) -> JsonMap:
    mission = dashboard.get("mission") if isinstance(dashboard.get("mission"), dict) else {}
    return {
        "id": _string(mission.get("id"), default="unknown"),
        "objective": _string(mission.get("objective"), default="unknown"),
        "next_safe_action": _string(dashboard.get("next_safe_action"), default="unknown"),
    }


def _proof_lines(evidence: JsonMap, audit: JsonMap) -> list[str]:
    lines: list[str] = []
    recorded_count = _int(audit.get("recorded_event_count"))
    bundle_count = _int(audit.get("runprint_bundle_count") or evidence.get("bundle_count"))
    gate_count = _int(audit.get("gate_count"))
    if gate_count:
        lines.append(f"Agent Gate recorded {gate_count} intent receipt(s).")
    if recorded_count:
        lines.append(f"RunPrint recorded {recorded_count} execution evidence receipt(s).")
    elif bundle_count:
        lines.append(f"RunPrint has {bundle_count} planned evidence bundle(s).")
    if not lines:
        lines.append("Plan evidence exists, but no Agent Gate or RunPrint receipt has been attached yet.")
    return lines


def _attention_lines(inbox: JsonMap, audit: JsonMap) -> list[str]:
    lines: list[str] = []
    pending = _int(inbox.get("pending_count"))
    blocked = _int(inbox.get("blocked_count"))
    needs_evidence = _int(inbox.get("needs_evidence_count"))
    if pending:
        lines.append(f"{pending} action(s) need human approval.")
    if blocked:
        lines.append(f"{blocked} action(s) are blocked.")
    if needs_evidence or audit.get("status") == "needs_evidence":
        lines.append("RunPrint evidence is missing for at least one gate receipt.")
    if audit.get("status") == "missing_gate":
        lines.append("No Agent Gate receipt exists yet.")
    return lines


def _plain_language(report: MissionStatusReport) -> tuple[str, ...]:
    if report.status == "recorded":
        return (
            "Agent asked for power.",
            "DelegationHQ checked the passport.",
            "Human approval and RunPrint proof are in the ledger.",
        )
    if report.status == "ready_for_recording":
        return (
            "The gate allowed the work.",
            "The proof bundle is planned.",
            "Now record what actually happened.",
        )
    if report.status == "planned":
        return (
            "The mission has a dry-run plan.",
            "No agent action has been gated yet.",
            "Create an Agent Gate receipt before real work.",
        )
    if report.status == "needs_attention":
        return (
            "Something is waiting: approval, proof, or review.",
            "Resolve that before giving the agent more power.",
        )
    if report.status == "blocked":
        return ("DelegationHQ stopped the action.", "Change the request or passport before retrying.")
    return ("Review the ledger before moving forward.",)


def _next_actions(status: str, ledger_source: str, primary_action_id: str | None) -> list[str]:
    if status == "recorded" and primary_action_id:
        return [
            f"delegation agent-packet --ledger {ledger_source} --action-id {primary_action_id}",
            f"delegation agent-audit --ledger {ledger_source}",
        ]
    if status == "ready_for_recording" and primary_action_id:
        return [
            f"delegation runprint-ingest --ledger {ledger_source} --action-id {primary_action_id} --recording-id REC --bundle-id BUNDLE --artifact PATH",
            f"delegation mission-status --ledger {ledger_source}",
        ]
    if status == "needs_attention" and primary_action_id:
        return [
            f"delegation approval-inbox --ledger {ledger_source}",
            f"delegation approval-decision --ledger {ledger_source} --action-id {primary_action_id} --decision approve --approver NAME",
        ]
    if status == "planned":
        return [
            "delegation agent-gate Harnessfile.yaml AGENT --action ACTION --target TARGET --ledger LEDGER --write",
            f"delegation mission-status --ledger {ledger_source}",
        ]
    return [f"delegation ledger {ledger_source}", f"delegation agent-audit --ledger {ledger_source}"]


def _primary_action_id(inbox: JsonMap) -> str | None:
    items = inbox.get("items") if isinstance(inbox.get("items"), list) else []
    for item in items:
        if isinstance(item, dict):
            value = item.get("action_id")
            if isinstance(value, str) and value.strip():
                return value
    return None


def _string(value: T.Any, *, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def _int(value: T.Any) -> int:
    return value if isinstance(value, int) else 0
