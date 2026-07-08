#!/usr/bin/env python3
"""Ingest Bring Your Own Agent result packets into a DelegationHQ ledger."""

from __future__ import annotations

import json
import typing as T
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from delegation_bot.agent_packet import build_agent_packet_report
from delegation_bot.harness_plan import LedgerEvent
from delegation_bot.runprint_ingest import RUNPRINT_INGEST_SCHEMA_VERSION


JsonMap = dict[str, T.Any]
AGENT_RESULT_SCHEMA_VERSION = "delegation.agent-result.v1"
AGENT_RESULT_INGEST_SCHEMA_VERSION = "delegation.agent-result-ingest.v1"
RESULT_STATUSES = {"completed", "failed", "blocked", "needs_attention", "partial"}


@dataclass(frozen=True)
class AgentResultIngestReport:
    schema_version: str
    status: str
    ledger_source: str
    result_source: str
    action_id: str
    packet_id: str | None
    agent_id: str | None
    result_status: str | None
    changed_resources: tuple[str, ...] = ()
    evidence_recording_id: str | None = None
    runprint_recording_id: str | None = None
    evidence_bundle_id: str | None = None
    evidence_tool: str = "runprint"
    artifact_count: int = 0
    warnings: tuple[str, ...] = ()
    next_action: str = ""
    events: tuple[LedgerEvent, ...] = field(default=(), repr=False, compare=False)

    @property
    def blocked(self) -> bool:
        return self.status in {
            "blocked",
            "duplicate_recording",
            "invalid_result",
            "missing_action",
            "needs_approval",
            "needs_evidence",
            "needs_review",
            "packet_not_ready",
        }

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "ledger_source": self.ledger_source,
            "result_source": self.result_source,
            "action_id": self.action_id,
            "packet_id": self.packet_id,
            "agent_id": self.agent_id,
            "result_status": self.result_status,
            "changed_resources": list(self.changed_resources),
            "evidence_recording_id": self.evidence_recording_id,
            "runprint_recording_id": self.runprint_recording_id,
            "evidence_bundle_id": self.evidence_bundle_id,
            "evidence_tool": self.evidence_tool,
            "artifact_count": self.artifact_count,
            "warnings": list(self.warnings),
            "next_action": self.next_action,
            "event_count": len(self.events),
            "event_types": [event.type for event in self.events],
        }


def load_agent_result(path: Path) -> JsonMap:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Agent result could not be read: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Agent result JSON error: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Agent result must be a JSON object")
    return data


def build_agent_result_ingest_report(
    ledger_events: T.Sequence[JsonMap],
    *,
    result: JsonMap,
    result_source: str,
    ledger_source: str = "<memory>",
    action_id: str | None = None,
    timestamp: str | None = None,
) -> AgentResultIngestReport:
    clean_action_id = _string(
        action_id
        or result.get("action_id")
        or result.get("target_action_id")
        or result.get("gate_action_id")
    )
    if not clean_action_id:
        return _blocked_report(
            status="missing_action",
            ledger_source=ledger_source,
            result_source=result_source,
            action_id="",
            warning="action_id is required",
        )

    packet_report = build_agent_packet_report(
        ledger_events,
        action_id=clean_action_id,
        ledger_source=ledger_source,
    )
    if not packet_report.packet:
        return _blocked_report(
            status=packet_report.status,
            ledger_source=ledger_source,
            result_source=result_source,
            action_id=clean_action_id,
            warning="No Agent Packet could be built for this result.",
            extra_warnings=packet_report.warnings,
        )

    packet = packet_report.packet
    packet_agent = packet.get("agent") if isinstance(packet.get("agent"), dict) else {}
    expected_agent_id = _string(packet_agent.get("id"))
    packet_id = _string(packet.get("packet_id"))
    result_status = _string(result.get("status"))
    result_agent_id = _string(result.get("agent_id") or result.get("agent"))
    result_packet_id = _string(result.get("packet_id"))
    changed_resources = tuple(_string_list(result.get("changed_resources")))
    evidence_tool = _string(result.get("evidence_tool") or result.get("recorder") or "runprint", default="runprint")
    recording_id = _string(
        result.get("evidence_recording_id")
        or result.get("runprint_recording_id")
        or _nested_string(result, "evidence", "recording_id")
        or _nested_string(result, "runprint", "recording_id")
    )
    bundle_id = _string(result.get("evidence_bundle_id") or _nested_string(result, "evidence", "bundle_id"))
    artifacts = tuple(_artifacts_from_result(result, result_source=result_source))
    warnings: list[str] = []

    if packet_report.status == "recorded":
        warnings.append("This action already has recorded evidence.")
        return _blocked_report(
            status="duplicate_recording",
            ledger_source=ledger_source,
            result_source=result_source,
            action_id=clean_action_id,
            packet_id=packet_id,
            agent_id=expected_agent_id or result_agent_id or None,
            result_status=result_status or None,
            changed_resources=changed_resources,
            evidence_recording_id=recording_id or None,
            runprint_recording_id=recording_id or None,
            evidence_bundle_id=bundle_id or None,
            evidence_tool=evidence_tool,
            artifact_count=len(artifacts),
            extra_warnings=tuple(warnings),
            next_action="Open a new Agent Gate receipt if this work must run again.",
        )

    if packet_report.status != "ready_for_agent":
        warnings.append(f"Agent Packet is `{packet_report.status}` and is not ready for execution.")
        return _blocked_report(
            status=packet_report.status if packet_report.status in {"needs_approval", "needs_review", "blocked"} else "packet_not_ready",
            ledger_source=ledger_source,
            result_source=result_source,
            action_id=clean_action_id,
            packet_id=packet_id,
            agent_id=expected_agent_id or result_agent_id or None,
            result_status=result_status or None,
            changed_resources=changed_resources,
            evidence_recording_id=recording_id or None,
            runprint_recording_id=recording_id or None,
            evidence_bundle_id=bundle_id or None,
            evidence_tool=evidence_tool,
            artifact_count=len(artifacts),
            extra_warnings=tuple(warnings),
            next_action="Approve, review, or unblock the Agent Packet before ingesting a worker result.",
        )

    _validate_result_identity(
        result,
        action_id=clean_action_id,
        packet_id=packet_id,
        expected_agent_id=expected_agent_id,
        result_agent_id=result_agent_id,
        warnings=warnings,
    )
    if not result_status:
        warnings.append("Result must include `status`.")
    elif result_status not in RESULT_STATUSES:
        warnings.append("Result status must be one of: " + ", ".join(sorted(RESULT_STATUSES)) + ".")
    if "summary" not in result or not _string(result.get("summary")):
        warnings.append("Result must include a short `summary`.")
    if "changed_resources" not in result or not isinstance(result.get("changed_resources"), list):
        warnings.append("Result must include `changed_resources` as a list.")
    if not recording_id:
        warnings.append("Result must include `evidence_recording_id` or `runprint_recording_id`.")
    if not bundle_id:
        warnings.append("Result must include `evidence_bundle_id`.")

    warnings.extend(_scope_warnings(packet, changed_resources))
    blocking_warnings = tuple(
        warning
        for warning in warnings
        if warning.startswith("Result ")
        or warning.startswith("Result status")
        or warning.startswith("Agent result")
        or warning.endswith("is required.")
        or warning.startswith("Changed resource touches a blocked secret")
    )
    if blocking_warnings:
        return _blocked_report(
            status="needs_evidence" if any("evidence" in warning or "recording" in warning for warning in blocking_warnings) else "invalid_result",
            ledger_source=ledger_source,
            result_source=result_source,
            action_id=clean_action_id,
            packet_id=packet_id,
            agent_id=expected_agent_id or result_agent_id or None,
            result_status=result_status or None,
            changed_resources=changed_resources,
            evidence_recording_id=recording_id or None,
            runprint_recording_id=recording_id or None,
            evidence_bundle_id=bundle_id or None,
            evidence_tool=evidence_tool,
            artifact_count=len(artifacts),
            extra_warnings=tuple(warnings),
            next_action="Fix the agent result JSON, then run `delegation agent-result-ingest` again.",
        )

    event_time = timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    start_sequence = len(ledger_events) + 1
    run_id = _run_id(ledger_events) or f"agent-result-{_event_id_part(clean_action_id)}"
    summary = _string(result.get("summary"), default="Agent result ingested.")
    outputs = result.get("outputs") if isinstance(result.get("outputs"), dict) else {}
    used_tools = _string_list(result.get("used_tools"))
    touched_data = _string_list(result.get("touched_data"))
    agent_id = expected_agent_id or result_agent_id or "unknown-agent"
    result_event = LedgerEvent(
        run_id=run_id,
        sequence=start_sequence,
        timestamp=event_time,
        type="agent.result.reported",
        status=result_status,
        message=f"Agent `{agent_id}` returned result `{result_status}` for `{clean_action_id}`.",
        action_id=clean_action_id,
        details={
            "schema_version": AGENT_RESULT_INGEST_SCHEMA_VERSION,
            "result_schema_version": _string(result.get("schema_version"), default=AGENT_RESULT_SCHEMA_VERSION),
            "adapter": "delegation.agent_result",
            "agent_id": agent_id,
            "packet_id": packet_id,
            "target_action_id": clean_action_id,
            "result_status": result_status,
            "summary": summary,
            "changed_resources": list(changed_resources),
            "outputs": outputs,
            "used_tools": used_tools,
            "touched_data": touched_data,
            "artifacts": artifacts,
            "evidence_recording_id": recording_id,
            "evidence_tool": evidence_tool,
            "runprint_recording_id": recording_id,
            "evidence_bundle_id": bundle_id,
            "source": result_source,
            "ingested": True,
        },
    )
    runprint_event = LedgerEvent(
        run_id=run_id,
        sequence=start_sequence + 1,
        timestamp=event_time,
        type="runprint.recording.completed",
        status="completed" if result_status in {"completed", "partial"} else result_status,
        message=f"Recorder evidence from agent result ingested for `{clean_action_id}`.",
        action_id=clean_action_id,
        details={
            "schema_version": RUNPRINT_INGEST_SCHEMA_VERSION,
            "adapter": f"{evidence_tool}.agent_result",
            "recorder": evidence_tool,
            "target_action_id": clean_action_id,
            "agent_id": agent_id,
            "packet_id": packet_id,
            "recording_id": recording_id,
            "evidence_recording_id": recording_id,
            "evidence_tool": evidence_tool,
            "evidence_bundle_id": bundle_id,
            "artifact_manifest": artifacts,
            "artifact_count": len(artifacts),
            "summary": summary,
            "source": result_source,
            "ingested": True,
            "capture_mode": "agent-result",
        },
    )
    return AgentResultIngestReport(
        schema_version=AGENT_RESULT_INGEST_SCHEMA_VERSION,
        status="recorded",
        ledger_source=ledger_source,
        result_source=result_source,
        action_id=clean_action_id,
        packet_id=packet_id,
        agent_id=agent_id,
        result_status=result_status,
        changed_resources=changed_resources,
        evidence_recording_id=recording_id,
        runprint_recording_id=recording_id,
        evidence_bundle_id=bundle_id,
        evidence_tool=evidence_tool,
        artifact_count=len(artifacts),
        warnings=tuple(warnings),
        next_action="Run `delegation agent-audit --ledger LEDGER` and evals before increasing this agent's autonomy.",
        events=(result_event, runprint_event),
    )


def render_agent_result_ingest_report(report: AgentResultIngestReport) -> str:
    lines = [
        "Agent Result Ingest",
        "",
        f"Status: {report.status}",
        f"Ledger: {report.ledger_source}",
        f"Result: {report.result_source}",
        f"Action: {report.action_id or 'unknown'}",
        f"Agent: {report.agent_id or 'unknown'}",
        f"Packet: {report.packet_id or 'unknown'}",
        f"Result status: {report.result_status or 'unknown'}",
        f"Changed resources: {_join_or_none(report.changed_resources)}",
        f"Evidence tool: {report.evidence_tool}",
        f"Recording: {report.evidence_recording_id or report.runprint_recording_id or 'missing'}",
        f"Bundle: {report.evidence_bundle_id or 'missing'}",
        f"Artifacts: {report.artifact_count}",
    ]
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    if report.events:
        lines.extend(["", "Recorded events:"])
        lines.extend(f"- {event.type} [{event.status}]" for event in report.events)
    lines.extend(["", "Next:", f"- {report.next_action or 'Review the result before continuing.'}"])
    return "\n".join(lines)


def _validate_result_identity(
    result: JsonMap,
    *,
    action_id: str,
    packet_id: str,
    expected_agent_id: str,
    result_agent_id: str,
    warnings: list[str],
) -> None:
    result_action_id = _string(result.get("action_id") or result.get("target_action_id") or result.get("gate_action_id"))
    result_packet_id = _string(result.get("packet_id"))
    if result_action_id and result_action_id != action_id:
        warnings.append(f"Agent result action_id `{result_action_id}` does not match `{action_id}`.")
    if result_packet_id and result_packet_id != packet_id:
        warnings.append(f"Agent result packet_id `{result_packet_id}` does not match `{packet_id}`.")
    if result_agent_id and expected_agent_id and result_agent_id != expected_agent_id:
        warnings.append(f"Agent result agent_id `{result_agent_id}` does not match `{expected_agent_id}`.")


def _scope_warnings(packet: JsonMap, changed_resources: T.Sequence[str]) -> tuple[str, ...]:
    boundary = packet.get("permission_boundary") if isinstance(packet.get("permission_boundary"), dict) else {}
    requested = packet.get("requested_work") if isinstance(packet.get("requested_work"), dict) else {}
    allowed = set(_string_list(boundary.get("allowed_data")))
    allowed.update(_string_list(boundary.get("expected_outputs")))
    target = _string(requested.get("target"))
    if target:
        allowed.add(target)
    warnings: list[str] = []
    for resource in changed_resources:
        lowered = resource.lower()
        if any(secret_word in lowered for secret_word in ("secret", "credential", ".env", "token")):
            warnings.append(f"Changed resource touches a blocked secret-like path: `{resource}`.")
            continue
        if allowed and not _matches_any_scope(resource, allowed):
            warnings.append(f"Changed resource `{resource}` is not explicitly listed in the agent passport scope.")
    return tuple(warnings)


def _matches_any_scope(resource: str, allowed: set[str]) -> bool:
    clean_resource = resource.strip().lower()
    for scope in allowed:
        clean_scope = scope.strip().lower()
        if not clean_scope:
            continue
        if clean_scope in {"workspace", "repository", "repo"}:
            return True
        if clean_resource == clean_scope or clean_resource.startswith(clean_scope.rstrip("/") + "/"):
            return True
        if clean_scope in clean_resource:
            return True
    return False


def _artifacts_from_result(result: JsonMap, *, result_source: str) -> T.Iterator[JsonMap]:
    raw = result.get("artifacts")
    if not isinstance(raw, list):
        evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
        raw = evidence.get("artifacts")
    artifacts: list[JsonMap] = []
    if isinstance(raw, list):
        for index, item in enumerate(raw, start=1):
            artifact = _artifact_from_value(item, index=index)
            if artifact:
                artifacts.append(artifact)
    if not artifacts:
        artifacts.append(
            {
                "id": Path(result_source).stem or "agent-result",
                "kind": "agent-result",
                "path": result_source,
                "required": True,
            }
        )
    yield from artifacts


def _artifact_from_value(value: T.Any, *, index: int) -> JsonMap | None:
    if isinstance(value, dict):
        artifact_id = _string(value.get("id") or value.get("name") or value.get("path"), default=f"artifact-{index}")
        return {
            "id": artifact_id,
            "kind": _string(value.get("kind") or value.get("type"), default="artifact"),
            "path": _string(value.get("path") or value.get("url"), default=artifact_id),
            "required": bool(value.get("required", True)),
        }
    if isinstance(value, str) and value.strip():
        path = value.strip()
        return {
            "id": Path(path).name or f"artifact-{index}",
            "kind": "artifact",
            "path": path,
            "required": True,
        }
    return None


def _blocked_report(
    *,
    status: str,
    ledger_source: str,
    result_source: str,
    action_id: str,
    warning: str | None = None,
    extra_warnings: tuple[str, ...] = (),
    packet_id: str | None = None,
    agent_id: str | None = None,
    result_status: str | None = None,
    changed_resources: tuple[str, ...] = (),
    evidence_recording_id: str | None = None,
    runprint_recording_id: str | None = None,
    evidence_bundle_id: str | None = None,
    evidence_tool: str = "runprint",
    artifact_count: int = 0,
    next_action: str = "Review the Agent Packet and result JSON before retrying.",
) -> AgentResultIngestReport:
    warnings = tuple(item for item in ((warning,) if warning else ()) + extra_warnings if item)
    return AgentResultIngestReport(
        schema_version=AGENT_RESULT_INGEST_SCHEMA_VERSION,
        status=status,
        ledger_source=ledger_source,
        result_source=result_source,
        action_id=action_id,
        packet_id=packet_id,
        agent_id=agent_id,
        result_status=result_status,
        changed_resources=changed_resources,
        evidence_recording_id=evidence_recording_id,
        runprint_recording_id=runprint_recording_id,
        evidence_bundle_id=evidence_bundle_id,
        evidence_tool=evidence_tool,
        artifact_count=artifact_count,
        warnings=warnings,
        next_action=next_action,
        events=(),
    )


def _nested_string(data: JsonMap, parent: str, child: str) -> str:
    nested = data.get(parent) if isinstance(data.get(parent), dict) else {}
    return _string(nested.get(child))


def _run_id(events: T.Sequence[JsonMap]) -> str | None:
    for event in events:
        value = event.get("run_id")
        if isinstance(value, str) and value.strip():
            return value
    return None


def _event_id_part(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    return "_".join(part for part in cleaned.split("_") if part) or "unknown"


def _join_or_none(values: T.Sequence[str]) -> str:
    return ", ".join(values) if values else "none"


def _string_list(value: T.Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _string(value: T.Any, *, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
