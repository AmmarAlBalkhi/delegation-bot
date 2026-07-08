#!/usr/bin/env python3
"""Agent handoff packets for Bring Your Own Agent workflows."""

from __future__ import annotations

import hashlib
import typing as T
from dataclasses import dataclass


JsonMap = dict[str, T.Any]
AGENT_PACKET_SCHEMA_VERSION = "delegation.agent-packet.v1"


@dataclass(frozen=True)
class AgentPacketReport:
    schema_version: str
    status: str
    ledger_source: str
    action_id: str
    packet: JsonMap | None
    warnings: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return self.status in {"missing_action", "blocked"}

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "ledger_source": self.ledger_source,
            "action_id": self.action_id,
            "packet": self.packet,
            "warnings": list(self.warnings),
        }


def build_agent_packet_report(
    ledger_events: T.Sequence[JsonMap],
    *,
    action_id: str,
    ledger_source: str = "<memory>",
) -> AgentPacketReport:
    clean_action_id = _string(action_id)
    if not clean_action_id:
        return AgentPacketReport(
            schema_version=AGENT_PACKET_SCHEMA_VERSION,
            status="missing_action",
            ledger_source=ledger_source,
            action_id="",
            packet=None,
            warnings=("action_id is required",),
        )

    gate_event = _find_gate_event(ledger_events, clean_action_id)
    if gate_event is None:
        return AgentPacketReport(
            schema_version=AGENT_PACKET_SCHEMA_VERSION,
            status="missing_action",
            ledger_source=ledger_source,
            action_id=clean_action_id,
            packet=None,
            warnings=(f"No Agent Gate receipt found for action_id `{clean_action_id}`.",),
        )

    gate = _gate_details(gate_event)
    agent = gate.get("agent") if isinstance(gate.get("agent"), dict) else {}
    approval = _latest_approval(ledger_events, clean_action_id)
    recorded = _has_runprint_recording(ledger_events, clean_action_id)
    decision = _string(gate.get("decision") or gate_event.get("status"), default="unknown")
    status = _packet_status(decision, approval, recorded)
    can_execute = status in {"ready_for_agent", "recorded"}
    packet = {
        "schema_version": AGENT_PACKET_SCHEMA_VERSION,
        "packet_id": _packet_id(clean_action_id, gate_event),
        "ledger_source": ledger_source,
        "action_id": clean_action_id,
        "status": status,
        "can_execute": can_execute,
        "agent": {
            "id": _string(gate.get("agent_id") or agent.get("id"), default="unknown-agent"),
            "name": _string(agent.get("name"), default=_string(gate.get("agent_id"), default="unknown-agent")),
            "runtime_type": _string(agent.get("runtime_type"), default="unknown"),
            "endpoint": agent.get("endpoint") if isinstance(agent.get("endpoint"), dict) else {},
            "autonomy_level": _string(agent.get("autonomy_level"), default="unknown"),
            "risk_level": _string(agent.get("risk_level") or gate.get("effective_risk"), default="medium"),
            "model": agent.get("model") if isinstance(agent.get("model"), str) else None,
        },
        "requested_work": {
            "action": _string(gate.get("action") or gate.get("requested_action"), default="unknown-action"),
            "target": _string(gate.get("target"), default="unknown-target"),
            "effective_risk": _string(gate.get("effective_risk"), default="medium"),
            "gate_decision": decision,
            "gate_sequence": gate_event.get("sequence") if isinstance(gate_event.get("sequence"), int) else None,
        },
        "permission_boundary": {
            "capabilities": _string_list(agent.get("capabilities")),
            "allowed_tools": _string_list(agent.get("allowed_tools")),
            "allowed_data": _string_list(agent.get("allowed_data")),
            "expected_outputs": _string_list(agent.get("expected_outputs")),
            "forbidden": _forbidden_lines(can_execute),
        },
        "required_controls": {
            "approvals": _string_list(gate.get("matched_approvals") or gate.get("required_approvals")),
            "evidence": _string_list(gate.get("required_evidence")),
            "promotion_evals": _string_list(agent.get("promotion_evals")),
        },
        "current_receipts": {
            "approval": approval,
            "runprint_recorded": recorded,
            "gate_recorded": True,
        },
        "instructions": _instructions(can_execute, recorded),
        "return_contract": {
            "schema_version": "delegation.agent-result.v1",
            "ingest_command": (
                f"delegation agent-result-ingest --ledger {ledger_source} "
                f"--action-id {clean_action_id} --result .delegation/agent-result.json"
            ),
            "must_return": [
                "schema_version",
                "packet_id",
                "action_id",
                "agent_id",
                "status",
                "summary",
                "changed_resources",
                "evidence_bundle_id",
                "runprint_recording_id",
                "artifacts",
            ],
            "allowed_statuses": ["completed", "failed", "blocked", "needs_attention", "partial"],
            "must_not_return": ["secrets", "raw credentials", "unapproved external writes"],
            "example": {
                "schema_version": "delegation.agent-result.v1",
                "packet_id": _packet_id(clean_action_id, gate_event),
                "action_id": clean_action_id,
                "agent_id": _string(gate.get("agent_id") or agent.get("id"), default="unknown-agent"),
                "status": "completed",
                "summary": "One short sentence describing what happened.",
                "changed_resources": [_string(gate.get("target"), default="workspace")],
                "runprint_recording_id": "rec-...",
                "evidence_bundle_id": "bundle-...",
                "artifacts": [{"id": "runprint-ledger", "kind": "jsonl", "path": ".delegation/run.jsonl"}],
            },
        },
    }
    return AgentPacketReport(
        schema_version=AGENT_PACKET_SCHEMA_VERSION,
        status=status,
        ledger_source=ledger_source,
        action_id=clean_action_id,
        packet=packet,
        warnings=(),
    )


def render_agent_packet_report(report: AgentPacketReport) -> str:
    lines = [
        "Agent Packet",
        "",
        f"Status: {report.status}",
        f"Ledger: {report.ledger_source}",
        f"Action: {report.action_id or 'unknown'}",
    ]
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    if not report.packet:
        lines.extend(["", "Next:", "- Create an Agent Gate receipt before exporting an agent packet."])
        return "\n".join(lines)

    packet = report.packet
    agent = packet["agent"]
    work = packet["requested_work"]
    controls = packet["required_controls"]
    receipts = packet["current_receipts"]
    lines.extend(
        [
            f"Can execute: {str(packet['can_execute']).lower()}",
            "",
            "Agent:",
            f"- id: {agent['id']}",
            f"- runtime: {agent['runtime_type']}",
            f"- autonomy: {agent['autonomy_level']}",
            "",
            "Requested work:",
            f"- action: {work['action']}",
            f"- target: {work['target']}",
            f"- risk: {work['effective_risk']}",
            f"- gate: {work['gate_decision']}",
            "",
            "Required controls:",
            "- approvals: " + _join_or_none(controls["approvals"]),
            "- evidence: " + _join_or_none(controls["evidence"]),
            "- promotion evals: " + _join_or_none(controls["promotion_evals"]),
            "",
            "Receipts:",
            f"- approval: {receipts['approval']['decision'] if receipts['approval'] else 'none'}",
            f"- RunPrint recorded: {str(receipts['runprint_recorded']).lower()}",
            "",
            "Instructions:",
        ]
    )
    lines.extend(f"- {instruction}" for instruction in packet["instructions"])
    lines.extend(
        [
            "",
            "Return contract:",
            f"- schema: {packet['return_contract']['schema_version']}",
            f"- ingest: {packet['return_contract']['ingest_command']}",
            "",
            "Next:",
            "- Send this JSON packet to the custom agent, then ingest its result JSON back into the ledger.",
        ]
    )
    return "\n".join(lines)


def _packet_status(decision: str, approval: JsonMap | None, recorded: bool) -> str:
    if decision == "block":
        return "blocked"
    if approval and approval.get("decision") == "block":
        return "blocked"
    if recorded:
        return "recorded"
    if decision == "approval_required" and not (approval and approval.get("decision") == "approve"):
        return "needs_approval"
    if decision == "warn":
        return "needs_review"
    return "ready_for_agent"


def _instructions(can_execute: bool, recorded: bool) -> list[str]:
    if recorded:
        return [
            "This action already has recorded RunPrint evidence.",
            "Do not repeat execution unless DelegationHQ issues a new Agent Gate receipt.",
            "Use the packet for review, replay, or eval context.",
        ]
    if can_execute:
        return [
            "Do only the requested work.",
            "Stay inside allowed tools, data, and expected outputs.",
            "Record execution with RunPrint and return the recording ids.",
            "Do not promote your own autonomy.",
        ]
    return [
        "Do not execute yet.",
        "Wait for the missing approval or review receipt.",
        "Use this packet only to prepare or explain the requested work.",
    ]


def _forbidden_lines(can_execute: bool) -> list[str]:
    lines = [
        "secret access unless explicitly approved",
        "external writes outside the requested target",
        "tool or data access outside the passport",
        "self-promotion without eval evidence",
    ]
    if not can_execute:
        lines.insert(0, "live execution before DelegationHQ clears the packet")
    return lines


def _find_gate_event(events: T.Sequence[JsonMap], action_id: str) -> JsonMap | None:
    for event in events:
        if event.get("type") == "agent.gate.previewed" and event.get("action_id") == action_id:
            return event
    return None


def _gate_details(event: JsonMap) -> JsonMap:
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    gate = details.get("agent_gate") if isinstance(details.get("agent_gate"), dict) else {}
    return gate


def _latest_approval(events: T.Sequence[JsonMap], action_id: str) -> JsonMap | None:
    latest: tuple[int, JsonMap] | None = None
    for event in events:
        event_type = event.get("type") if isinstance(event.get("type"), str) else ""
        if event_type not in {"approval.granted", "approval.denied"}:
            continue
        if event.get("action_id") != action_id:
            continue
        sequence = event.get("sequence") if isinstance(event.get("sequence"), int) else -1
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        decision = "approve" if event_type == "approval.granted" else "block"
        approval = {
            "decision": decision,
            "approver": _string(details.get("approver"), default="unknown"),
            "reason": _string(details.get("reason")),
            "sequence": sequence if sequence >= 0 else None,
        }
        if latest is None or latest[0] <= sequence:
            latest = (sequence, approval)
    return latest[1] if latest else None


def _has_runprint_recording(events: T.Sequence[JsonMap], action_id: str) -> bool:
    for event in events:
        event_type = event.get("type") if isinstance(event.get("type"), str) else ""
        if not event_type.startswith("runprint.recording.") or event_type.endswith(".planned"):
            continue
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        if event.get("action_id") == action_id or details.get("target_action_id") == action_id:
            return True
    return False


def _packet_id(action_id: str, event: JsonMap) -> str:
    raw = f"{action_id}|{event.get('run_id')}|{event.get('sequence')}".encode("utf-8")
    return "agent_packet_" + hashlib.sha256(raw).hexdigest()[:20]


def _join_or_none(values: T.Sequence[str]) -> str:
    return ", ".join(values) if values else "none"


def _string_list(value: T.Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _string(value: T.Any, *, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
