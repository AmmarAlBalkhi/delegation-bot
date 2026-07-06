#!/usr/bin/env python3
"""Export DelegationHQ ledgers to a local OpenTelemetry-like JSON shape."""

from __future__ import annotations

import hashlib
import json
import typing as T
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from delegation_bot.eval_feedback import sanitize_details


JsonMap = dict[str, T.Any]


class OtelExportError(ValueError):
    """Raised when a ledger cannot be exported to telemetry JSON."""


@dataclass(frozen=True)
class OtelExport:
    source: str
    data: JsonMap

    def to_dict(self) -> JsonMap:
        return self.data


def build_otel_export(
    events: T.Sequence[JsonMap],
    *,
    source: str = "<memory>",
    service_version: str | None = None,
    environment: str = "local",
) -> OtelExport:
    if not events:
        raise OtelExportError("Cannot export an empty ledger.")

    sanitized_events = [sanitize_details(event) for event in events]
    run_ids = _run_ids(sanitized_events)
    traces = [_build_trace(run_id, _events_for_run(sanitized_events, run_id), source) for run_id in run_ids]
    data: JsonMap = {
        "format": "delegation.otel.trace.v1",
        "source": source,
        "resource": {
            "service.name": "delegationhq",
            "service.version": service_version or _package_version(),
            "deployment.environment": environment,
            "delegation.ledger.schema": "ledger.v1",
        },
        "traces": traces,
        "logs": [
            log
            for trace in traces
            for log in trace.get("logs", [])
        ],
        "warnings": list(_ordering_warnings(sanitized_events)),
    }
    return OtelExport(source=source, data=data)


def write_otel_export(export: OtelExport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(export.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_otel_export(export: OtelExport) -> str:
    data = export.to_dict()
    trace_count = len(data.get("traces", []))
    span_count = sum(len(trace.get("spans", [])) for trace in data.get("traces", []))
    log_count = len(data.get("logs", []))
    lines = [
        "OpenTelemetry export",
        "",
        f"Source: {data.get('source')}",
        f"Format: {data.get('format')}",
        f"Traces: {trace_count}",
        f"Spans: {span_count}",
        f"Logs: {log_count}",
    ]
    warnings = data.get("warnings") if isinstance(data.get("warnings"), list) else []
    if warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines)


def _build_trace(run_id: str, events: T.Sequence[JsonMap], source: str) -> JsonMap:
    trace_id = _hex_id(f"trace:{run_id}", 32)
    root_span_id = _hex_id(f"span:{run_id}:root", 16)
    root_span = _root_span(run_id, trace_id, root_span_id, events, source)
    action_spans = [
        _action_span(run_id, trace_id, root_span_id, action_id, action_events)
        for action_id, action_events in _group_action_events(events).items()
    ]
    spans = [root_span, *action_spans]
    span_ids = {None: root_span_id, "": root_span_id}
    span_ids.update({span["attributes"]["delegation.action.id"]: span["span_id"] for span in action_spans})
    logs = [_log_record(event, trace_id, span_ids.get(_event_action_id(event), root_span_id)) for event in events]
    return {
        "trace_id": trace_id,
        "run_id": run_id,
        "root_span_id": root_span_id,
        "spans": spans,
        "logs": logs,
    }


def _root_span(run_id: str, trace_id: str, span_id: str, events: T.Sequence[JsonMap], source: str) -> JsonMap:
    plan = _plan_payload(events)
    attributes: JsonMap = {
        "delegation.run.id": run_id,
        "delegation.mode": str(plan.get("mode", "unknown")),
        "delegation.harness.id": str(plan.get("id", "unknown")),
        "delegation.objective": str(plan.get("objective", "")),
        "delegation.ledger.source": source,
    }
    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": None,
        "name": "delegation.run",
        "kind": "internal",
        "start_time": _timestamp(events[0]),
        "end_time": _timestamp(events[-1]),
        "status": _status_for_events(events),
        "attributes": attributes,
        "events": [_span_event(event) for event in events if not _event_action_id(event)],
    }


def _action_span(
    run_id: str,
    trace_id: str,
    root_span_id: str,
    action_id: str,
    events: T.Sequence[JsonMap],
) -> JsonMap:
    action = _action_payload(events)
    adapter = _event_adapter(events[-1])
    attributes: JsonMap = {
        "delegation.run.id": run_id,
        "delegation.action.id": action_id,
        "delegation.action.type": str(action.get("type", "unknown")),
        "delegation.action.risk": str(action.get("risk", "unknown")),
        "delegation.action.requires_approval": bool(action.get("requires_approval", False)),
        "delegation.adapter.id": adapter or str(action.get("adapter", "unknown")),
        "delegation.adapter.status": _event_status(events[-1]),
        "delegation.dry_run": _dry_run(events),
    }
    return {
        "trace_id": trace_id,
        "span_id": _hex_id(f"span:{run_id}:{action_id}", 16),
        "parent_span_id": root_span_id,
        "name": "delegation.action",
        "kind": "internal",
        "start_time": _timestamp(events[0]),
        "end_time": _timestamp(events[-1]),
        "status": _status_for_events(events),
        "attributes": attributes,
        "events": [_span_event(event) for event in events],
    }


def _span_event(event: JsonMap) -> JsonMap:
    return {
        "name": _otel_event_name(_event_type(event)),
        "time": _timestamp(event),
        "attributes": {
            "delegation.ledger.event_type": _event_type(event),
            "delegation.event.status": _event_status(event),
            "delegation.sequence": _event_sequence(event),
            "delegation.action.id": _event_action_id(event),
            "delegation.event.details": _details(event),
        },
    }


def _log_record(event: JsonMap, trace_id: str, span_id: str) -> JsonMap:
    return {
        "timestamp": _timestamp(event),
        "trace_id": trace_id,
        "span_id": span_id,
        "severity_text": _severity(_event_status(event)),
        "body": _event_message(event),
        "attributes": {
            "delegation.run.id": _event_run_id(event),
            "delegation.sequence": _event_sequence(event),
            "delegation.event.type": _event_type(event),
            "delegation.event.status": _event_status(event),
            "delegation.action.id": _event_action_id(event),
        },
    }


def _ordering_warnings(events: T.Sequence[JsonMap]) -> tuple[str, ...]:
    warnings: list[str] = []
    for run_id in _run_ids(events):
        run_events = _events_for_run(events, run_id)
        sequences = [_event_sequence(event) for event in run_events]
        if any(sequence is None for sequence in sequences):
            warnings.append(f"Run `{run_id}` has events without integer sequence numbers.")
            continue
        concrete = [sequence for sequence in sequences if isinstance(sequence, int)]
        expected = list(range(1, len(concrete) + 1))
        if concrete != expected:
            warnings.append(f"Run `{run_id}` has non-contiguous sequence numbers.")
    return tuple(warnings)


def _events_for_run(events: T.Sequence[JsonMap], run_id: str) -> list[JsonMap]:
    return [event for event in events if (_event_run_id(event) or "unknown-run") == run_id]


def _run_ids(events: T.Sequence[JsonMap]) -> tuple[str, ...]:
    values: list[str] = []
    for event in events:
        run_id = _event_run_id(event) or "unknown-run"
        if run_id not in values:
            values.append(run_id)
    return tuple(values)


def _group_action_events(events: T.Sequence[JsonMap]) -> dict[str, list[JsonMap]]:
    grouped: dict[str, list[JsonMap]] = {}
    for event in events:
        action_id = _event_action_id(event)
        if action_id:
            grouped.setdefault(action_id, []).append(event)
    return grouped


def _status_for_events(events: T.Sequence[JsonMap]) -> JsonMap:
    statuses = {_event_status(event) for event in events}
    if statuses & {"failed", "error"}:
        return {"code": "error"}
    if statuses & {"blocked"}:
        return {"code": "unset", "message": "blocked"}
    return {"code": "ok"}


def _severity(status: str) -> str:
    if status in {"failed", "error"}:
        return "ERROR"
    if status in {"blocked", "skipped"}:
        return "WARN"
    return "INFO"


def _otel_event_name(event_type: str) -> str:
    mapping = {
        "plan.compiled": "delegation.plan.compiled",
        "eval.result": "delegation.eval.result",
        "github.issue.planned": "delegation.github.issue.planned",
        "github.issue.created": "delegation.github.issue.created",
        "github.issue.updated": "delegation.github.issue.updated",
    }
    if event_type.startswith("dry_run."):
        return "delegation.dry_run.event"
    if event_type.startswith("adapter."):
        return "delegation.adapter.event"
    if event_type.startswith("promotion."):
        return "delegation.promotion.event"
    return mapping.get(event_type, f"delegation.{event_type}")


def _plan_payload(events: T.Sequence[JsonMap]) -> JsonMap:
    for event in events:
        details = _details(event)
        plan = details.get("plan")
        if isinstance(plan, dict):
            return plan
    return {}


def _action_payload(events: T.Sequence[JsonMap]) -> JsonMap:
    for event in events:
        details = _details(event)
        action = details.get("action")
        if isinstance(action, dict):
            return action
    return {}


def _dry_run(events: T.Sequence[JsonMap]) -> bool:
    for event in events:
        details = _details(event)
        if isinstance(details.get("dry_run"), bool):
            return bool(details["dry_run"])
        adapter_result = details.get("adapter_result")
        if isinstance(adapter_result, dict) and isinstance(adapter_result.get("dry_run"), bool):
            return bool(adapter_result["dry_run"])
    return True


def _details(event: JsonMap) -> JsonMap:
    details = event.get("details")
    return details if isinstance(details, dict) else {}


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


def _timestamp(event: JsonMap) -> str:
    value = event.get("timestamp")
    return value if isinstance(value, str) and value.strip() else ""


def _event_adapter(event: JsonMap) -> str | None:
    details = _details(event)
    adapter = details.get("adapter")
    if isinstance(adapter, str) and adapter.strip():
        return adapter
    action = details.get("action")
    if isinstance(action, dict) and isinstance(action.get("adapter"), str):
        return action["adapter"]
    adapter_result = details.get("adapter_result")
    if isinstance(adapter_result, dict) and isinstance(adapter_result.get("adapter_id"), str):
        return adapter_result["adapter_id"]
    return None


def _hex_id(value: str, length: int) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _package_version() -> str:
    try:
        return metadata.version("delegationhq")
    except metadata.PackageNotFoundError:
        return "0.1.0a0"
