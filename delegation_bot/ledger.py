#!/usr/bin/env python3
"""Read and render Delegation Bot JSONL run ledgers."""

from __future__ import annotations

import json
import typing as T
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


JsonMap = dict[str, T.Any]


class LedgerError(ValueError):
    """Raised when a run ledger cannot be read or rendered."""


@dataclass(frozen=True)
class LedgerFilter:
    event_type: str | None = None
    status: str | None = None
    action_id: str | None = None
    adapter: str | None = None

    def is_active(self) -> bool:
        return any((self.event_type, self.status, self.action_id, self.adapter))

    def matches(self, event: JsonMap) -> bool:
        if self.event_type and _event_type(event) != self.event_type:
            return False
        if self.status and _event_status(event) != self.status:
            return False
        if self.action_id and _event_action_id(event) != self.action_id:
            return False
        if self.adapter and _event_adapter(event) != self.adapter:
            return False
        return True

    def to_dict(self) -> JsonMap:
        return {
            "type": self.event_type,
            "status": self.status,
            "action_id": self.action_id,
            "adapter": self.adapter,
        }


@dataclass(frozen=True)
class AdapterEvidence:
    adapter: str
    action_id: str
    event_type: str
    status: str
    output_keys: tuple[str, ...]
    evidence: JsonMap = field(default_factory=dict)
    details: JsonMap = field(default_factory=dict)

    def to_dict(self) -> JsonMap:
        return {
            "adapter": self.adapter,
            "action_id": self.action_id,
            "event_type": self.event_type,
            "status": self.status,
            "output_keys": list(self.output_keys),
            "evidence": self.evidence,
            "details": self.details,
        }


@dataclass(frozen=True)
class EvalEvidence:
    eval_id: str
    status: str
    message: str
    event_type: str
    sequence: int | None

    def to_dict(self) -> JsonMap:
        return {
            "eval_id": self.eval_id,
            "status": self.status,
            "message": self.message,
            "event_type": self.event_type,
            "sequence": self.sequence,
        }


@dataclass(frozen=True)
class LedgerView:
    source: str
    total_events: int
    shown_events: tuple[JsonMap, ...]
    run_ids: tuple[str, ...]
    status_counts: JsonMap
    type_counts: JsonMap
    adapter_counts: JsonMap
    adapter_evidence: tuple[AdapterEvidence, ...]
    eval_evidence: tuple[EvalEvidence, ...]
    filters: LedgerFilter
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> JsonMap:
        return {
            "source": self.source,
            "total_events": self.total_events,
            "shown_event_count": len(self.shown_events),
            "run_ids": list(self.run_ids),
            "status_counts": self.status_counts,
            "type_counts": self.type_counts,
            "adapter_counts": self.adapter_counts,
            "adapter_evidence": [item.to_dict() for item in self.adapter_evidence],
            "eval_evidence": [item.to_dict() for item in self.eval_evidence],
            "filters": self.filters.to_dict(),
            "warnings": list(self.warnings),
            "events": list(self.shown_events),
        }


def load_ledger_events(path: Path) -> list[JsonMap]:
    events: list[JsonMap] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                data = json.loads(line)
                if not isinstance(data, dict):
                    raise LedgerError(f"Ledger line {line_number} must be a JSON object")
                events.append(data)
    except OSError as exc:
        raise LedgerError(str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise LedgerError(f"Ledger JSON error: {exc}") from exc
    return events


def build_ledger_view(
    events: T.Sequence[JsonMap],
    source: str = "<memory>",
    ledger_filter: LedgerFilter | None = None,
    limit: int = 12,
) -> LedgerView:
    active_filter = ledger_filter or LedgerFilter()
    filtered = [event for event in events if active_filter.matches(event)]
    shown = filtered[-max(limit, 0) :] if limit else filtered
    evidence_events = filtered if active_filter.is_active() else list(events)
    warnings = _ledger_warnings(events)

    status_counts = _counter_to_dict(Counter(_event_status(event) for event in events))
    type_counts = _counter_to_dict(Counter(_event_type(event) for event in events))
    adapter_counts = _counter_to_dict(Counter(adapter for event in events if (adapter := _event_adapter(event))))
    run_ids = tuple(sorted({run_id for event in events if (run_id := _event_run_id(event))}))

    return LedgerView(
        source=source,
        total_events=len(events),
        shown_events=tuple(shown),
        run_ids=run_ids,
        status_counts=status_counts,
        type_counts=type_counts,
        adapter_counts=adapter_counts,
        adapter_evidence=tuple(_adapter_evidence(evidence_events)),
        eval_evidence=tuple(_eval_evidence(evidence_events)),
        filters=active_filter,
        warnings=warnings,
    )


def render_ledger_view(view: LedgerView) -> str:
    lines = [
        "Ledger report",
        "",
        f"Source: {view.source}",
        f"Events: {view.total_events}",
        f"Runs: {', '.join(view.run_ids) if view.run_ids else 'none'}",
        f"Statuses: {_format_counts(view.status_counts)}",
        f"Adapters: {_format_counts(view.adapter_counts)}",
    ]

    if view.filters.is_active():
        lines.append(f"Filters: {_format_filters(view.filters)}")

    if view.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in view.warnings)

    lines.extend(["", "Adapter evidence:"])
    if view.adapter_evidence:
        for item in view.adapter_evidence:
            evidence = _format_key_values(item.evidence) or "none"
            outputs = ", ".join(item.output_keys) or "none"
            lines.append(f"- {item.adapter} {item.action_id} [{item.status}]")
            lines.append(f"  event: {item.event_type}")
            lines.append(f"  outputs: {outputs}")
            lines.append(f"  evidence: {evidence}")
    else:
        lines.append("- none")

    lines.extend(["", "Eval evidence:"])
    if view.eval_evidence:
        for item in view.eval_evidence:
            sequence = f" seq={item.sequence}" if item.sequence is not None else ""
            lines.append(f"- {item.eval_id}: {item.status}{sequence}")
            lines.append(f"  {item.message}")
    else:
        lines.append("- none")

    lines.extend(["", f"Recent events ({len(view.shown_events)} shown):"])
    if view.shown_events:
        for event in view.shown_events:
            sequence = _event_sequence(event)
            prefix = f"{sequence}. " if sequence is not None else "- "
            action = _event_action_id(event)
            action_text = f" action={action}" if action else ""
            lines.append(f"{prefix}{_event_status(event)} {_event_type(event)}{action_text}")
    else:
        lines.append("- none")

    return "\n".join(lines)


def _ledger_warnings(events: T.Sequence[JsonMap]) -> tuple[str, ...]:
    warnings: list[str] = []
    sequences = [_event_sequence(event) for event in events]
    if any(sequence is None for sequence in sequences):
        warnings.append("One or more events are missing integer sequence numbers.")
    concrete_sequences = [sequence for sequence in sequences if sequence is not None]
    expected = list(range(1, len(concrete_sequences) + 1))
    if concrete_sequences and concrete_sequences != expected:
        warnings.append("Event sequence numbers are not contiguous.")
    if not events:
        warnings.append("Ledger is empty.")
    return tuple(warnings)


def _adapter_evidence(events: T.Sequence[JsonMap]) -> T.Iterator[AdapterEvidence]:
    for event in events:
        details = _details(event)
        adapter_result = details.get("adapter_result")
        if not isinstance(adapter_result, dict):
            continue
        outputs = adapter_result.get("outputs") if isinstance(adapter_result.get("outputs"), dict) else {}
        evidence = adapter_result.get("evidence") if isinstance(adapter_result.get("evidence"), dict) else {}
        adapter = _event_adapter(event) or str(adapter_result.get("adapter_id") or "unknown")
        action_id = _event_action_id(event) or "unknown"
        yield AdapterEvidence(
            adapter=adapter,
            action_id=action_id,
            event_type=_event_type(event),
            status=_event_status(event),
            output_keys=tuple(sorted(outputs)),
            evidence=evidence,
            details={
                key: value
                for key, value in details.items()
                if key not in {"adapter_result", "action", "contract"}
            },
        )


def _eval_evidence(events: T.Sequence[JsonMap]) -> T.Iterator[EvalEvidence]:
    for event in events:
        details = _details(event)
        eval_id = details.get("eval_id")
        eval_obj = details.get("eval") if isinstance(details.get("eval"), dict) else {}
        nested_id = eval_obj.get("id") if isinstance(eval_obj.get("id"), str) else None
        if _event_type(event) != "eval.result" and not eval_id and not nested_id:
            continue
        resolved_eval_id = str(eval_id or nested_id or "unknown")
        yield EvalEvidence(
            eval_id=resolved_eval_id,
            status=_event_status(event),
            message=_event_message(event),
            event_type=_event_type(event),
            sequence=_event_sequence(event),
        )


def _details(event: JsonMap) -> JsonMap:
    return event.get("details") if isinstance(event.get("details"), dict) else {}


def _event_run_id(event: JsonMap) -> str | None:
    value = event.get("run_id")
    return value if isinstance(value, str) and value.strip() else None


def _event_type(event: JsonMap) -> str:
    value = event.get("type")
    return value if isinstance(value, str) and value.strip() else "unknown"


def _event_status(event: JsonMap) -> str:
    value = event.get("status")
    return value if isinstance(value, str) and value.strip() else "unknown"


def _event_action_id(event: JsonMap) -> str | None:
    value = event.get("action_id")
    return value if isinstance(value, str) and value.strip() else None


def _event_message(event: JsonMap) -> str:
    value = event.get("message")
    return value if isinstance(value, str) else ""


def _event_sequence(event: JsonMap) -> int | None:
    value = event.get("sequence")
    return value if isinstance(value, int) else None


def _event_adapter(event: JsonMap) -> str | None:
    details = _details(event)
    adapter = details.get("adapter")
    if isinstance(adapter, str) and adapter.strip():
        return adapter

    action = details.get("action") if isinstance(details.get("action"), dict) else {}
    action_adapter = action.get("adapter")
    if isinstance(action_adapter, str) and action_adapter.strip():
        return action_adapter
    return None


def _counter_to_dict(counter: Counter[str]) -> JsonMap:
    return {key: counter[key] for key in sorted(counter)}


def _format_counts(counts: JsonMap) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in counts.items())


def _format_filters(ledger_filter: LedgerFilter) -> str:
    values = {
        key: value
        for key, value in ledger_filter.to_dict().items()
        if isinstance(value, str) and value.strip()
    }
    return _format_key_values(values) or "none"


def _format_key_values(values: JsonMap) -> str:
    if not values:
        return ""
    parts: list[str] = []
    for key in sorted(values):
        value = values[key]
        if isinstance(value, (dict, list)):
            value_text = json.dumps(value, sort_keys=True)
        else:
            value_text = str(value)
        parts.append(f"{key}={value_text}")
    return ", ".join(parts)
