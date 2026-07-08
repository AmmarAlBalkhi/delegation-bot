#!/usr/bin/env python3
"""Approval inbox data model for Agent Gate receipts."""

from __future__ import annotations

import hashlib
import typing as T
from dataclasses import dataclass
from datetime import datetime, timezone

from delegation_bot.agent_gate import build_agent_gate_audit_report
from delegation_bot.harness_plan import LedgerEvent


JsonMap = dict[str, T.Any]

APPROVAL_INBOX_SCHEMA_VERSION = "delegation.approval-inbox.v1"
APPROVAL_DECISION_SCHEMA_VERSION = "delegation.approval-decision.v1"
APPROVAL_DECISIONS = ("approve", "block")


@dataclass(frozen=True)
class ApprovalDecision:
    action_id: str
    decision: str
    approver: str
    reason: str
    sequence: int | None
    timestamp: str | None

    def to_dict(self) -> JsonMap:
        return {
            "action_id": self.action_id,
            "decision": self.decision,
            "approver": self.approver,
            "reason": self.reason,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class ApprovalInboxItem:
    id: str
    action_id: str
    request_id: str | None
    sequence: int | None
    title: str
    status: str
    requested_by: str | None
    request_summary: str | None
    agent_id: str
    action: str
    target: str
    risk: str
    gate_decision: str
    evidence_status: str
    audit_outcome: str
    required_approvals: tuple[str, ...]
    provided_approvals: tuple[str, ...]
    required_evidence: tuple[str, ...]
    latest_decision: ApprovalDecision | None
    available_decisions: tuple[str, ...]
    message: str
    next_action: str

    def to_dict(self) -> JsonMap:
        return {
            "id": self.id,
            "action_id": self.action_id,
            "request_id": self.request_id,
            "sequence": self.sequence,
            "title": self.title,
            "status": self.status,
            "requested_by": self.requested_by,
            "request_summary": self.request_summary,
            "agent_id": self.agent_id,
            "action": self.action,
            "target": self.target,
            "risk": self.risk,
            "gate_decision": self.gate_decision,
            "evidence_status": self.evidence_status,
            "audit_outcome": self.audit_outcome,
            "required_approvals": list(self.required_approvals),
            "provided_approvals": list(self.provided_approvals),
            "required_evidence": list(self.required_evidence),
            "latest_decision": self.latest_decision.to_dict() if self.latest_decision else None,
            "available_decisions": list(self.available_decisions),
            "message": self.message,
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class ApprovalInboxReport:
    schema_version: str
    status: str
    ledger_source: str
    item_count: int
    pending_count: int
    approved_count: int
    blocked_count: int
    needs_evidence_count: int
    ready_count: int
    items: tuple[ApprovalInboxItem, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "ledger_source": self.ledger_source,
            "item_count": self.item_count,
            "pending_count": self.pending_count,
            "approved_count": self.approved_count,
            "blocked_count": self.blocked_count,
            "needs_evidence_count": self.needs_evidence_count,
            "ready_count": self.ready_count,
            "items": [item.to_dict() for item in self.items],
            "warnings": list(self.warnings),
            "next_action": self.next_action,
        }

    @property
    def next_action(self) -> str:
        if self.pending_count:
            return "Record a human decision with `delegation approval-decision --ledger LEDGER --action-id ACTION_ID --decision approve|block --approver NAME`."
        if self.needs_evidence_count:
            return "Add recorder evidence or request more evidence before promotion."
        if self.item_count:
            return "Execute under recorder control, then run evals before promotion."
        return "Run `delegation agent-gate ... --ledger LEDGER --write` to create approval cards."


@dataclass(frozen=True)
class ApprovalDecisionReceipt:
    schema_version: str
    status: str
    ledger_source: str
    action_id: str
    decision: str
    approver: str
    reason: str
    event_type: str
    message: str
    next_action: str

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "ledger_source": self.ledger_source,
            "action_id": self.action_id,
            "decision": self.decision,
            "approver": self.approver,
            "reason": self.reason,
            "event_type": self.event_type,
            "message": self.message,
            "next_action": self.next_action,
        }


def build_approval_inbox_report(
    ledger_events: T.Sequence[JsonMap],
    *,
    ledger_source: str = "<memory>",
) -> ApprovalInboxReport:
    gate_events = tuple(_agent_gate_events(ledger_events))
    decisions = _approval_decisions_by_action(ledger_events)
    requests = _action_requests_by_action(ledger_events)
    audit = build_agent_gate_audit_report(ledger_events, ledger_source=ledger_source)
    audit_by_sequence = {item.gate_sequence: item for item in audit.items if item.gate_sequence is not None}

    items = tuple(
        _inbox_item(
            event,
            decisions.get(_event_action_id(event)),
            audit_by_sequence.get(_event_sequence(event)),
            requests.get(_event_action_id(event)),
        )
        for event in gate_events
    )
    pending_count = sum(1 for item in items if item.status == "pending_approval")
    approved_count = sum(1 for item in items if item.status == "approved")
    blocked_count = sum(1 for item in items if item.status in {"blocked_by_gate", "blocked_by_human"})
    needs_evidence_count = sum(1 for item in items if item.status == "needs_evidence")
    ready_count = sum(1 for item in items if item.status in {"ready_for_recording", "recorded"})
    return ApprovalInboxReport(
        schema_version=APPROVAL_INBOX_SCHEMA_VERSION,
        status=_report_status(items),
        ledger_source=ledger_source,
        item_count=len(items),
        pending_count=pending_count,
        approved_count=approved_count,
        blocked_count=blocked_count,
        needs_evidence_count=needs_evidence_count,
        ready_count=ready_count,
        items=items,
        warnings=() if items else ("No Agent Gate receipts were found for the approval inbox.",),
    )


def build_approval_decision_events(
    ledger_events: T.Sequence[JsonMap],
    *,
    action_id: str,
    decision: str,
    approver: str,
    reason: str = "",
    run_id: str | None = None,
    start_sequence: int | None = None,
    timestamp: str | None = None,
) -> list[LedgerEvent]:
    normalized_decision = decision.strip().lower()
    if normalized_decision not in APPROVAL_DECISIONS:
        raise ValueError("decision must be `approve` or `block`")
    clean_action_id = _string_value(action_id)
    if not clean_action_id:
        raise ValueError("action_id is required")
    clean_approver = _string_value(approver)
    if not clean_approver:
        raise ValueError("approver is required")
    if not any(_event_action_id(event) == clean_action_id for event in _agent_gate_events(ledger_events)):
        raise ValueError(f"No Agent Gate receipt found for action_id `{clean_action_id}`")

    event_type = "approval.granted" if normalized_decision == "approve" else "approval.denied"
    status = "approved" if normalized_decision == "approve" else "blocked"
    event_time = timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sequence = start_sequence if start_sequence is not None else len(ledger_events) + 1
    ledger_run_id = run_id or _run_id(ledger_events) or f"approval-{_event_id_part(clean_action_id)}"
    clean_reason = _string_value(reason)
    return [
        LedgerEvent(
            run_id=ledger_run_id,
            sequence=sequence,
            timestamp=event_time,
            type=event_type,
            status=status,
            message=f"Human decision `{normalized_decision}` recorded for `{clean_action_id}` by `{clean_approver}`.",
            action_id=clean_action_id,
            details={
                "schema_version": APPROVAL_DECISION_SCHEMA_VERSION,
                "adapter": "delegation.approval",
                "approval_id": _approval_id(clean_action_id, normalized_decision, clean_approver, clean_reason),
                "decision": normalized_decision,
                "approver": clean_approver,
                "reason": clean_reason,
                "target_action_id": clean_action_id,
                "dry_run": True,
            },
        )
    ]


def build_approval_decision_receipt(
    event: LedgerEvent,
    *,
    ledger_source: str,
) -> ApprovalDecisionReceipt:
    details = event.details
    decision = _string_value(details.get("decision"), default="unknown")
    approver = _string_value(details.get("approver"), default="unknown")
    reason = _string_value(details.get("reason"))
    return ApprovalDecisionReceipt(
        schema_version=APPROVAL_DECISION_SCHEMA_VERSION,
        status=event.status,
        ledger_source=ledger_source,
        action_id=event.action_id or "unknown",
        decision=decision,
        approver=approver,
        reason=reason,
        event_type=event.type,
        message=event.message,
        next_action="Run `delegation approval-inbox --ledger LEDGER` or `delegation agent-audit --ledger LEDGER` to review the updated mission state.",
    )


def render_approval_inbox_report(report: ApprovalInboxReport) -> str:
    lines = [
        "Approval Inbox",
        "",
        f"Status: {report.status}",
        f"Ledger: {report.ledger_source}",
        f"Cards: {report.item_count}",
        f"Pending approval: {report.pending_count}",
        f"Approved: {report.approved_count}",
        f"Blocked: {report.blocked_count}",
        f"Needs evidence: {report.needs_evidence_count}",
        f"Ready/recorded: {report.ready_count}",
    ]

    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)

    lines.extend(["", "Cards:"])
    if not report.items:
        lines.append("- none")
    for item in report.items:
        lines.append(f"- [{item.status}] {item.title}")
        lines.append(f"  action_id: {item.action_id}")
        if item.requested_by:
            lines.append(f"  requested by: {item.requested_by}")
        if item.request_summary:
            lines.append(f"  summary: {item.request_summary}")
        lines.append(f"  risk: {item.risk}; gate: {item.gate_decision}; evidence: {item.evidence_status}")
        if item.required_approvals:
            lines.append("  approvals: " + ", ".join(item.required_approvals))
        if item.latest_decision:
            lines.append(f"  latest decision: {item.latest_decision.decision} by {item.latest_decision.approver}")
        lines.append(f"  next: {item.next_action}")

    lines.extend(["", "Next:", f"- {report.next_action}"])
    return "\n".join(lines)


def render_approval_decision_receipt(receipt: ApprovalDecisionReceipt) -> str:
    lines = [
        "Approval Decision",
        "",
        f"Status: {receipt.status}",
        f"Ledger: {receipt.ledger_source}",
        f"Action: {receipt.action_id}",
        f"Decision: {receipt.decision}",
        f"Approver: {receipt.approver}",
    ]
    if receipt.reason:
        lines.append(f"Reason: {receipt.reason}")
    lines.extend(["", receipt.message, "", "Next:", f"- {receipt.next_action}"])
    return "\n".join(lines)


def _inbox_item(
    event: JsonMap,
    decision: ApprovalDecision | None,
    audit_item: T.Any | None,
    request: JsonMap | None,
) -> ApprovalInboxItem:
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    gate = details.get("agent_gate") if isinstance(details.get("agent_gate"), dict) else {}
    action_id = _event_action_id(event) or f"gate-{_event_sequence(event) or 'unknown'}"
    agent_id = _string_value(gate.get("agent_id") or details.get("agent_id"), default="unknown-agent")
    action = _string_value(gate.get("action") or details.get("requested_action"), default="unknown-action")
    target = _string_value(gate.get("target") or details.get("target"), default="unknown-target")
    risk = _string_value(gate.get("effective_risk") or details.get("effective_risk"), default="medium")
    gate_decision = _string_value(gate.get("decision") or details.get("decision") or event.get("status"), default="unknown")
    required_approvals = tuple(_string_list(gate.get("matched_approvals") or gate.get("required_approvals")))
    provided_approvals = tuple(_string_list(gate.get("provided_approvals")))
    required_evidence = tuple(_string_list(gate.get("required_evidence")))
    evidence_status = _string_value(getattr(audit_item, "evidence_status", ""), default="missing")
    audit_outcome = _string_value(getattr(audit_item, "outcome", ""), default="unknown")
    status = _item_status(gate_decision, decision, audit_outcome)
    requested_by = _string_value(request.get("requested_by") if request else "") or None
    request_summary = _string_value(request.get("summary") if request else "") or None
    request_id = _string_value(request.get("request_id") if request else "") or None
    title = request_summary or f"{agent_id} wants {action} on {target}"
    available_decisions = _available_decisions(status)
    return ApprovalInboxItem(
        id=action_id,
        action_id=action_id,
        request_id=request_id,
        sequence=_event_sequence(event),
        title=title,
        status=status,
        requested_by=requested_by,
        request_summary=request_summary,
        agent_id=agent_id,
        action=action,
        target=target,
        risk=risk,
        gate_decision=gate_decision,
        evidence_status=evidence_status,
        audit_outcome=audit_outcome,
        required_approvals=required_approvals,
        provided_approvals=provided_approvals,
        required_evidence=required_evidence,
        latest_decision=decision,
        available_decisions=available_decisions,
        message=_item_message(status),
        next_action=_item_next_action(status, action_id),
    )


def _item_status(gate_decision: str, decision: ApprovalDecision | None, audit_outcome: str) -> str:
    if decision and decision.decision == "block":
        return "blocked_by_human"
    if gate_decision == "block" or audit_outcome == "blocked_by_gate":
        return "blocked_by_gate"
    if audit_outcome == "recorded":
        return "recorded"
    if decision and decision.decision == "approve":
        return "approved"
    if gate_decision == "approval_required" or audit_outcome == "waiting_for_approval":
        return "pending_approval"
    if audit_outcome == "evidence_missing":
        return "needs_evidence"
    if audit_outcome == "recording_planned":
        return "ready_for_recording"
    if gate_decision == "warn" or audit_outcome == "review_warning":
        return "warning"
    return "ready_for_recording"


def _available_decisions(status: str) -> tuple[str, ...]:
    if status == "pending_approval":
        return ("approve", "block")
    if status in {"needs_evidence", "warning"}:
        return ("block",)
    return ()


def _item_message(status: str) -> str:
    return {
        "pending_approval": "Human approval is required before this intent can move forward.",
        "approved": "Human approval has been recorded for this intent.",
        "blocked_by_human": "A human blocked this intent.",
        "blocked_by_gate": "Agent Gate blocked this intent before execution.",
        "needs_evidence": "The intent passed the gate, but recorder evidence is missing.",
        "ready_for_recording": "The intent can move to recorder-controlled execution.",
        "recorded": "An evidence tool recorded execution proof for this intent.",
        "warning": "This intent needs review before autonomy increases.",
    }.get(status, "Review this approval card before continuing.")


def _item_next_action(status: str, action_id: str) -> str:
    if status == "pending_approval":
        return f"Run `delegation approval-decision --ledger LEDGER --action-id {action_id} --decision approve --approver NAME` or block it."
    if status == "approved":
        return "Execute under recorder control, then run evals before promotion."
    if status in {"blocked_by_human", "blocked_by_gate"}:
        return "Change the request, passport, target, or approval decision before retrying."
    if status == "needs_evidence":
        return "Add recorder evidence before promotion."
    if status == "recorded":
        return "Run evals and promotion checks against the ledger."
    if status == "warning":
        return "Review the warning and request more evidence if needed."
    return "Execute under recorder control, then append recorded evidence."


def _report_status(items: T.Sequence[ApprovalInboxItem]) -> str:
    statuses = {item.status for item in items}
    if not items:
        return "empty"
    if statuses & {"pending_approval", "needs_evidence", "warning"}:
        return "needs_attention"
    if statuses & {"blocked_by_human", "blocked_by_gate"}:
        return "blocked"
    return "ready"


def _agent_gate_events(events: T.Sequence[JsonMap]) -> T.Iterator[JsonMap]:
    for event in events:
        if event.get("type") == "agent.gate.previewed":
            yield event


def _approval_decisions_by_action(events: T.Sequence[JsonMap]) -> dict[str, ApprovalDecision]:
    decisions: dict[str, ApprovalDecision] = {}
    for event in events:
        event_type = event.get("type") if isinstance(event.get("type"), str) else ""
        if event_type not in {"approval.granted", "approval.denied"}:
            continue
        action_id = _event_action_id(event)
        if not action_id:
            continue
        sequence = _event_sequence(event)
        existing = decisions.get(action_id)
        if existing and existing.sequence is not None and sequence is not None and existing.sequence > sequence:
            continue
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        decision = "approve" if event_type == "approval.granted" else "block"
        decisions[action_id] = ApprovalDecision(
            action_id=action_id,
            decision=decision,
            approver=_string_value(details.get("approver"), default="unknown"),
            reason=_string_value(details.get("reason")),
            sequence=sequence,
            timestamp=_string_value(event.get("timestamp")) or None,
        )
    return decisions


def _action_requests_by_action(events: T.Sequence[JsonMap]) -> dict[str, JsonMap]:
    requests: dict[str, JsonMap] = {}
    for event in events:
        if event.get("type") != "action.requested":
            continue
        action_id = _event_action_id(event)
        if not action_id:
            continue
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        sequence = _event_sequence(event)
        existing = requests.get(action_id)
        existing_sequence = existing.get("sequence") if isinstance(existing, dict) else None
        if isinstance(existing_sequence, int) and isinstance(sequence, int) and existing_sequence > sequence:
            continue
        requests[action_id] = {
            "request_id": _string_value(details.get("request_id")),
            "requested_by": _string_value(details.get("requested_by")),
            "summary": _string_value(details.get("summary")),
            "sequence": sequence,
        }
    return requests


def _approval_id(action_id: str, decision: str, approver: str, reason: str) -> str:
    raw = f"{action_id}|{decision}|{approver}|{reason}".encode("utf-8")
    return "approval_" + hashlib.sha256(raw).hexdigest()[:20]


def _run_id(events: T.Sequence[JsonMap]) -> str | None:
    for event in events:
        value = event.get("run_id")
        if isinstance(value, str) and value.strip():
            return value
    return None


def _event_action_id(event: JsonMap) -> str | None:
    value = event.get("action_id")
    return value if isinstance(value, str) and value.strip() else None


def _event_sequence(event: JsonMap) -> int | None:
    value = event.get("sequence")
    return value if isinstance(value, int) else None


def _event_id_part(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    return "_".join(part for part in cleaned.split("_") if part) or "unknown"


def _string_list(value: T.Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _string_value(value: T.Any, *, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
