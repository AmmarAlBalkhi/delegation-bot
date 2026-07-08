#!/usr/bin/env python3
"""Ingest evidence from any DelegationHQ-compatible proof tool."""

from __future__ import annotations

import json
import typing as T
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from delegation_bot.harness_plan import LedgerEvent


JsonMap = dict[str, T.Any]
EVIDENCE_INGEST_SCHEMA_VERSION = "delegation.evidence-ingest.v1"


@dataclass(frozen=True)
class EvidenceArtifact:
    id: str
    kind: str
    path: str
    required: bool = True

    def to_dict(self) -> JsonMap:
        return {
            "id": self.id,
            "kind": self.kind,
            "path": self.path,
            "required": self.required,
        }


@dataclass(frozen=True)
class EvidenceIngestReceipt:
    schema_version: str
    status: str
    ledger_source: str
    action_id: str
    evidence_tool: str
    tool_kind: str
    recording_id: str
    evidence_bundle_id: str
    artifact_count: int
    source: str
    summary: str
    event_type: str
    message: str
    next_action: str

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "ledger_source": self.ledger_source,
            "action_id": self.action_id,
            "evidence_tool": self.evidence_tool,
            "tool_kind": self.tool_kind,
            "recording_id": self.recording_id,
            "evidence_bundle_id": self.evidence_bundle_id,
            "artifact_count": self.artifact_count,
            "source": self.source,
            "summary": self.summary,
            "event_type": self.event_type,
            "message": self.message,
            "next_action": self.next_action,
        }


def load_evidence_bundle(path: Path) -> JsonMap:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Evidence bundle could not be read: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Evidence bundle JSON error: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Evidence bundle must be a JSON object")
    return data


def evidence_artifacts_from_values(values: T.Sequence[str]) -> tuple[EvidenceArtifact, ...]:
    artifacts: list[EvidenceArtifact] = []
    for index, value in enumerate(values, start=1):
        clean = value.strip()
        if not clean:
            continue
        parts = clean.split(":", 2)
        if len(parts) == 3 and all(part.strip() for part in parts):
            artifact_id, kind, path = (part.strip() for part in parts)
        else:
            path = clean
            artifact_id = Path(clean).name or f"artifact-{index}"
            kind = "artifact"
        artifacts.append(EvidenceArtifact(id=artifact_id, kind=kind, path=path, required=True))
    return tuple(artifacts)


def build_evidence_recording_events(
    ledger_events: T.Sequence[JsonMap],
    *,
    evidence_tool: str | None = None,
    tool_kind: str | None = None,
    action_id: str | None = None,
    recording_id: str | None = None,
    evidence_bundle_id: str | None = None,
    artifacts: T.Sequence[EvidenceArtifact] = (),
    summary: str = "",
    source: str = "manual",
    bundle: JsonMap | None = None,
    run_id: str | None = None,
    start_sequence: int | None = None,
    timestamp: str | None = None,
) -> list[LedgerEvent]:
    bundle = bundle or {}
    clean_action_id = _string_value(
        action_id
        or bundle.get("action_id")
        or bundle.get("target_action_id")
        or bundle.get("gate_action_id")
    )
    if not clean_action_id:
        raise ValueError("action_id is required")
    if not any(_event_action_id(event) == clean_action_id for event in _agent_gate_events(ledger_events)):
        raise ValueError(f"No Agent Gate receipt found for action_id `{clean_action_id}`")

    clean_tool = _tool_id(
        evidence_tool
        or bundle.get("evidence_tool")
        or bundle.get("tool")
        or bundle.get("recorder")
        or _nested_string(bundle, "recording", "tool")
        or _nested_string(bundle, "recording_session", "recorder")
        or "manual"
    )
    clean_tool_kind = _string_value(tool_kind or bundle.get("tool_kind") or bundle.get("kind"), default="recorder")
    clean_recording_id = _string_value(
        recording_id
        or bundle.get("recording_id")
        or bundle.get("evidence_recording_id")
        or _nested_string(bundle, "recording", "id")
        or _nested_string(bundle, "recording_session", "recording_id")
    )
    clean_bundle_id = _string_value(
        evidence_bundle_id
        or bundle.get("evidence_bundle_id")
        or bundle.get("bundle_id")
        or _nested_string(bundle, "evidence_bundle", "evidence_bundle_id")
        or _nested_string(bundle, "bundle", "id")
    )
    if not clean_recording_id:
        raise ValueError("recording_id is required")
    if not clean_bundle_id:
        raise ValueError("evidence_bundle_id is required")

    artifact_manifest = tuple(artifacts) or _artifacts_from_bundle(bundle)
    if not artifact_manifest:
        raise ValueError("at least one artifact is required")

    clean_summary = _string_value(summary or bundle.get("summary") or bundle.get("description"), default="Evidence recorded.")
    clean_source = _string_value(source or bundle.get("source") or bundle.get("url"), default="manual")
    event_time = timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sequence = start_sequence if start_sequence is not None else len(ledger_events) + 1
    ledger_run_id = run_id or _run_id(ledger_events) or f"evidence-{_event_id_part(clean_action_id)}"

    return [
        LedgerEvent(
            run_id=ledger_run_id,
            sequence=sequence,
            timestamp=event_time,
            type="evidence.recording.completed",
            status="completed",
            message=f"Evidence tool `{clean_tool}` recorded proof for `{clean_action_id}`.",
            action_id=clean_action_id,
            details={
                "schema_version": EVIDENCE_INGEST_SCHEMA_VERSION,
                "adapter": f"{clean_tool}.evidence_ingest",
                "evidence_tool": clean_tool,
                "tool_kind": clean_tool_kind,
                "recorder": clean_tool,
                "target_action_id": clean_action_id,
                "recording_id": clean_recording_id,
                "evidence_recording_id": clean_recording_id,
                "evidence_bundle_id": clean_bundle_id,
                "artifact_manifest": [artifact.to_dict() for artifact in artifact_manifest],
                "artifact_count": len(artifact_manifest),
                "summary": clean_summary,
                "source": clean_source,
                "ingested": True,
                "capture_mode": "external",
            },
        )
    ]


def build_evidence_ingest_receipt(event: LedgerEvent, *, ledger_source: str) -> EvidenceIngestReceipt:
    details = event.details
    return EvidenceIngestReceipt(
        schema_version=EVIDENCE_INGEST_SCHEMA_VERSION,
        status=event.status,
        ledger_source=ledger_source,
        action_id=event.action_id or "unknown",
        evidence_tool=_string_value(details.get("evidence_tool") or details.get("recorder"), default="unknown"),
        tool_kind=_string_value(details.get("tool_kind"), default="recorder"),
        recording_id=_string_value(details.get("evidence_recording_id") or details.get("recording_id"), default="unknown"),
        evidence_bundle_id=_string_value(details.get("evidence_bundle_id"), default="unknown"),
        artifact_count=int(details.get("artifact_count")) if isinstance(details.get("artifact_count"), int) else 0,
        source=_string_value(details.get("source"), default="unknown"),
        summary=_string_value(details.get("summary")),
        event_type=event.type,
        message=event.message,
        next_action="Run `delegation agent-audit --ledger LEDGER` and `delegation approval-inbox --ledger LEDGER` to verify recorded evidence.",
    )


def render_evidence_ingest_receipt(receipt: EvidenceIngestReceipt) -> str:
    lines = [
        "Evidence Recording Ingest",
        "",
        f"Status: {receipt.status}",
        f"Ledger: {receipt.ledger_source}",
        f"Action: {receipt.action_id}",
        f"Tool: {receipt.evidence_tool} ({receipt.tool_kind})",
        f"Recording: {receipt.recording_id}",
        f"Bundle: {receipt.evidence_bundle_id}",
        f"Artifacts: {receipt.artifact_count}",
        f"Source: {receipt.source}",
    ]
    if receipt.summary:
        lines.append(f"Summary: {receipt.summary}")
    lines.extend(["", receipt.message, "", "Next:", f"- {receipt.next_action}"])
    return "\n".join(lines)


def _artifacts_from_bundle(bundle: JsonMap) -> tuple[EvidenceArtifact, ...]:
    raw = bundle.get("artifacts")
    if not isinstance(raw, list):
        evidence_bundle = bundle.get("evidence_bundle") if isinstance(bundle.get("evidence_bundle"), dict) else {}
        raw = evidence_bundle.get("artifact_manifest")
    if not isinstance(raw, list):
        raw = bundle.get("artifact_manifest")
    if not isinstance(raw, list):
        return ()

    artifacts: list[EvidenceArtifact] = []
    for index, item in enumerate(raw, start=1):
        if isinstance(item, dict):
            artifact_id = _string_value(item.get("id") or item.get("name") or item.get("path"), default=f"artifact-{index}")
            artifacts.append(
                EvidenceArtifact(
                    id=artifact_id,
                    kind=_string_value(item.get("kind") or item.get("type"), default="artifact"),
                    path=_string_value(item.get("path") or item.get("url"), default=artifact_id),
                    required=bool(item.get("required", True)),
                )
            )
        elif isinstance(item, str) and item.strip():
            artifact_id = Path(item).name or f"artifact-{index}"
            artifacts.append(EvidenceArtifact(id=artifact_id, kind="artifact", path=item.strip(), required=True))
    return tuple(artifacts)


def _agent_gate_events(events: T.Sequence[JsonMap]) -> T.Iterator[JsonMap]:
    for event in events:
        if event.get("type") == "agent.gate.previewed":
            yield event


def _event_action_id(event: JsonMap) -> str | None:
    value = event.get("action_id")
    return value if isinstance(value, str) and value.strip() else None


def _run_id(events: T.Sequence[JsonMap]) -> str | None:
    for event in events:
        value = event.get("run_id")
        if isinstance(value, str) and value.strip():
            return value
    return None


def _nested_string(data: JsonMap, parent: str, child: str) -> str:
    nested = data.get(parent) if isinstance(data.get(parent), dict) else {}
    value = nested.get(child)
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _event_id_part(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    return "_".join(part for part in cleaned.split("_") if part) or "unknown"


def _tool_id(value: T.Any) -> str:
    raw = value.strip().lower() if isinstance(value, str) and value.strip() else "manual"
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in raw)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "manual"


def _string_value(value: T.Any, *, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
