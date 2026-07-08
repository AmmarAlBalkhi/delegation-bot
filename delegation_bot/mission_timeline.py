#!/usr/bin/env python3
"""Mission timeline over DelegationHQ ledger events."""

from __future__ import annotations

import typing as T
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from delegation_bot.ledger import load_ledger_events
from delegation_bot.local_workspace import DEFAULT_WORKSPACE_AGENT_RUN_LEDGER


JsonMap = dict[str, T.Any]
TIMELINE_SCHEMA_VERSION = "delegation.mission-timeline.v1"


@dataclass(frozen=True)
class TimelineItem:
    id: str
    sequence: int | None
    timestamp: str | None
    stage: str
    status: str
    event_type: str
    title: str
    message: str
    action_id: str | None
    agent_id: str | None
    adapter: str | None
    risk: str | None
    evidence: tuple[str, ...]
    needs_attention: bool

    def to_dict(self) -> JsonMap:
        return {
            "id": self.id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "stage": self.stage,
            "status": self.status,
            "event_type": self.event_type,
            "title": self.title,
            "message": self.message,
            "action_id": self.action_id,
            "agent_id": self.agent_id,
            "adapter": self.adapter,
            "risk": self.risk,
            "evidence": list(self.evidence),
            "needs_attention": self.needs_attention,
        }


@dataclass(frozen=True)
class MissionTimelineReport:
    schema_version: str
    status: str
    ledger_source: str
    event_count: int
    shown_count: int
    stage_counts: JsonMap
    attention_count: int
    items: tuple[TimelineItem, ...]
    warnings: tuple[str, ...] = ()

    @property
    def next_action(self) -> str:
        if self.warnings and self.event_count == 0:
            return "Create a workspace plan or run an Agent Gate preview to start the timeline."
        if self.attention_count:
            return "Resolve the first timeline item that needs attention before increasing autonomy."
        if any(item.stage == "record" for item in self.items):
            return "Run evals and promotion checks against the recorded evidence."
        if any(item.stage == "approval" and item.status == "approved" for item in self.items):
            return "Execute under recorder control, then attach RunPrint evidence."
        if any(item.stage == "gate" for item in self.items):
            return "Record approval if required, then execute under recorder control."
        return "Create an Agent Gate receipt before real work."

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "ledger_source": self.ledger_source,
            "event_count": self.event_count,
            "shown_count": self.shown_count,
            "stage_counts": self.stage_counts,
            "attention_count": self.attention_count,
            "items": [item.to_dict() for item in self.items],
            "warnings": list(self.warnings),
            "next_action": self.next_action,
        }


def build_timeline_report(
    ledger_events: T.Sequence[JsonMap],
    *,
    ledger_source: str = "<memory>",
    limit: int = 20,
) -> MissionTimelineReport:
    """Build a compact timeline for the app and CLI."""

    all_items = tuple(_timeline_items(ledger_events))
    shown_limit = max(limit, 0)
    shown_items = all_items[-shown_limit:] if shown_limit else all_items
    attention_count = sum(1 for item in all_items if item.needs_attention)
    warnings = _warnings(ledger_events)
    return MissionTimelineReport(
        schema_version=TIMELINE_SCHEMA_VERSION,
        status=_timeline_status(all_items, warnings),
        ledger_source=ledger_source,
        event_count=len(ledger_events),
        shown_count=len(shown_items),
        stage_counts=dict(sorted(Counter(item.stage for item in all_items).items())),
        attention_count=attention_count,
        items=shown_items,
        warnings=warnings,
    )


def build_timeline_report_from_paths(
    *,
    ledger_path: Path | None = None,
    workspace_root: Path | None = None,
    limit: int = 20,
) -> MissionTimelineReport:
    """Load the ledger path, using workspace defaults when provided."""

    resolved_ledger = ledger_path
    if resolved_ledger is None and workspace_root is not None:
        resolved_ledger = workspace_root.resolve() / DEFAULT_WORKSPACE_AGENT_RUN_LEDGER
    if resolved_ledger is None:
        raise ValueError("--ledger is required unless --workspace is provided")
    if not resolved_ledger.exists():
        return MissionTimelineReport(
            schema_version=TIMELINE_SCHEMA_VERSION,
            status="missing",
            ledger_source=str(resolved_ledger),
            event_count=0,
            shown_count=0,
            stage_counts={},
            attention_count=0,
            items=(),
            warnings=(f"Ledger does not exist: {resolved_ledger}",),
        )
    events = load_ledger_events(resolved_ledger)
    return build_timeline_report(events, ledger_source=str(resolved_ledger), limit=limit)


def render_timeline_report(report: MissionTimelineReport) -> str:
    lines = [
        "DelegationHQ Mission Timeline",
        "",
        f"Status: {report.status}",
        f"Ledger: {report.ledger_source}",
        f"Events: {report.event_count}",
        f"Shown: {report.shown_count}",
        f"Attention: {report.attention_count}",
        f"Stages: {_format_counts(report.stage_counts)}",
    ]
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)

    lines.extend(["", "Timeline:"])
    if not report.items:
        lines.append("- none")
    for item in report.items:
        sequence = f"{item.sequence}. " if item.sequence is not None else "- "
        action = f" action={item.action_id}" if item.action_id else ""
        risk = f" risk={item.risk}" if item.risk else ""
        attention = " attention" if item.needs_attention else ""
        lines.append(f"{sequence}[{item.stage}] {item.status} {item.title}{action}{risk}{attention}")
        if item.message:
            lines.append(f"  {item.message}")
        if item.evidence:
            lines.append(f"  evidence: {', '.join(item.evidence)}")

    lines.extend(
        [
            "",
            "Plain language:",
            "- The timeline shows the mission in order: plan, gate, approve, execute, record, eval, feedback, promote.",
            "- It is read-only. It explains what happened and what still needs attention.",
            "",
            "Next:",
            f"- {report.next_action}",
        ]
    )
    return "\n".join(lines)


def _timeline_items(events: T.Sequence[JsonMap]) -> T.Iterator[TimelineItem]:
    for index, event in enumerate(events, start=1):
        event_type = _event_type(event)
        stage = _stage(event)
        status = _event_status(event)
        details = _details(event)
        gate = details.get("agent_gate") if isinstance(details.get("agent_gate"), dict) else {}
        risk = _string(gate.get("effective_risk") or details.get("effective_risk"))
        action_id = _event_action_id(event)
        title = _title(event)
        evidence = tuple(_evidence_labels(event))
        sequence = _event_sequence(event)
        yield TimelineItem(
            id=f"timeline-{sequence if sequence is not None else index}",
            sequence=sequence,
            timestamp=_string(event.get("timestamp")) or None,
            stage=stage,
            status=status,
            event_type=event_type,
            title=title,
            message=_event_message(event),
            action_id=action_id,
            agent_id=_agent_id(event),
            adapter=_adapter(event),
            risk=risk,
            evidence=evidence,
            needs_attention=_needs_attention(stage, status, event),
        )


def _stage(event: JsonMap) -> str:
    event_type = _event_type(event)
    if event_type == "plan.compiled":
        return "plan"
    if event_type == "agent.gate.previewed":
        return "gate"
    if event_type in {"approval.granted", "approval.denied"}:
        return "approval"
    if event_type.startswith("agent.execution."):
        return "execute"
    if event_type.startswith("runprint.") or "recording" in event_type:
        return "record"
    if event_type.startswith("eval."):
        return "eval"
    if "feedback" in event_type:
        return "feedback"
    if "promotion" in event_type or event_type.startswith("agent.promotion"):
        return "promote"
    if _adapter(event):
        return "adapter"
    return "ledger"


def _title(event: JsonMap) -> str:
    event_type = _event_type(event)
    if event_type == "plan.compiled":
        return "Mission plan compiled"
    if event_type == "agent.gate.previewed":
        agent = _agent_id(event) or "agent"
        action = _gate_value(event, "action") or "requested action"
        return f"{agent} requested {action}"
    if event_type == "approval.granted":
        return "Human approval recorded"
    if event_type == "approval.denied":
        return "Human block recorded"
    if event_type == "agent.execution.started":
        return "Agent execution started"
    if event_type in {"agent.execution.completed", "agent.execution.failed"}:
        return "Agent execution finished"
    if event_type == "runprint.recording.completed":
        return "RunPrint evidence recorded"
    if event_type == "eval.result":
        details = _details(event)
        return f"Eval {_string(details.get('eval_id'), default='unknown')} completed"
    if "feedback" in event_type:
        return "Feedback event recorded"
    if "promotion" in event_type:
        return "Promotion event recorded"
    return event_type.replace(".", " ").strip().title()


def _needs_attention(stage: str, status: str, event: JsonMap) -> bool:
    if status in {"failed", "blocked", "timed_out"}:
        return True
    if _event_type(event) == "agent.gate.previewed":
        gate_decision = _gate_value(event, "decision")
        return gate_decision in {"approval_required", "block", "warn"}
    if stage == "approval" and _event_type(event) == "approval.denied":
        return True
    return False


def _timeline_status(items: T.Sequence[TimelineItem], warnings: T.Sequence[str]) -> str:
    if not items:
        return "empty" if not warnings else "missing"
    if any(item.status in {"failed", "blocked", "timed_out"} for item in items):
        return "blocked"
    if any(item.needs_attention for item in items):
        return "needs_attention"
    if any(item.stage == "record" for item in items):
        return "recorded"
    if any(item.stage == "approval" for item in items):
        return "approved"
    if any(item.stage == "gate" for item in items):
        return "gated"
    return "planned"


def _warnings(events: T.Sequence[JsonMap]) -> tuple[str, ...]:
    if not events:
        return ("Ledger is empty.",)
    sequences = [_event_sequence(event) for event in events]
    if any(sequence is None for sequence in sequences):
        return ("One or more events are missing sequence numbers.",)
    concrete = [sequence for sequence in sequences if sequence is not None]
    if concrete != list(range(1, len(concrete) + 1)):
        return ("Timeline sequence numbers are not contiguous.",)
    return ()


def _evidence_labels(event: JsonMap) -> T.Iterator[str]:
    details = _details(event)
    adapter_result = details.get("adapter_result") if isinstance(details.get("adapter_result"), dict) else {}
    evidence = adapter_result.get("evidence") if isinstance(adapter_result.get("evidence"), dict) else {}
    for key in sorted(evidence):
        yield str(key)
    artifact_manifest = details.get("artifact_manifest")
    if isinstance(artifact_manifest, list):
        for item in artifact_manifest:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                yield item["id"]
    if isinstance(details.get("output_artifact"), str):
        yield "command-output"


def _gate_value(event: JsonMap, key: str) -> str | None:
    details = _details(event)
    gate = details.get("agent_gate") if isinstance(details.get("agent_gate"), dict) else {}
    return _string(gate.get(key)) or None


def _agent_id(event: JsonMap) -> str | None:
    return _gate_value(event, "agent_id") or _string(_details(event).get("agent_id")) or None


def _adapter(event: JsonMap) -> str | None:
    details = _details(event)
    adapter = _string(details.get("adapter"))
    if adapter:
        return adapter
    action = details.get("action") if isinstance(details.get("action"), dict) else {}
    return _string(action.get("adapter")) or None


def _details(event: JsonMap) -> JsonMap:
    return event.get("details") if isinstance(event.get("details"), dict) else {}


def _event_type(event: JsonMap) -> str:
    return _string(event.get("type"), default="unknown")


def _event_status(event: JsonMap) -> str:
    return _string(event.get("status"), default="unknown")


def _event_message(event: JsonMap) -> str:
    return _string(event.get("message"))


def _event_action_id(event: JsonMap) -> str | None:
    return _string(event.get("action_id")) or None


def _event_sequence(event: JsonMap) -> int | None:
    value = event.get("sequence")
    return value if isinstance(value, int) else None


def _string(value: T.Any, *, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def _format_counts(counts: JsonMap) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in counts.items())
