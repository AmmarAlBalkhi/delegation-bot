#!/usr/bin/env python3
"""Ingest external RunPrint recording evidence into a DelegationHQ ledger."""

from __future__ import annotations

import json
import typing as T
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from delegation_bot.harness_plan import LedgerEvent


JsonMap = dict[str, T.Any]
RUNPRINT_INGEST_SCHEMA_VERSION = "delegation.runprint-ingest.v1"


@dataclass(frozen=True)
class RunPrintArtifact:
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
class RunPrintIngestReceipt:
    schema_version: str
    status: str
    ledger_source: str
    action_id: str
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
            "recording_id": self.recording_id,
            "evidence_bundle_id": self.evidence_bundle_id,
            "artifact_count": self.artifact_count,
            "source": self.source,
            "summary": self.summary,
            "event_type": self.event_type,
            "message": self.message,
            "next_action": self.next_action,
        }


def load_runprint_bundle(path: Path) -> JsonMap:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"RunPrint bundle could not be read: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"RunPrint bundle JSON error: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("RunPrint bundle must be a JSON object")
    return data


def artifacts_from_values(values: T.Sequence[str]) -> tuple[RunPrintArtifact, ...]:
    artifacts: list[RunPrintArtifact] = []
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
        artifacts.append(RunPrintArtifact(id=artifact_id, kind=kind, path=path, required=True))
    return tuple(artifacts)


def build_runprint_recording_events(
    ledger_events: T.Sequence[JsonMap],
    *,
    action_id: str | None = None,
    recording_id: str | None = None,
    evidence_bundle_id: str | None = None,
    artifacts: T.Sequence[RunPrintArtifact] = (),
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

    clean_recording_id = _string_value(
        recording_id
        or bundle.get("recording_id")
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

    clean_summary = _string_value(summary or bundle.get("summary") or bundle.get("description"), default="RunPrint evidence recorded.")
    clean_source = _string_value(source or bundle.get("source") or bundle.get("url"), default="manual")
    event_time = timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sequence = start_sequence if start_sequence is not None else len(ledger_events) + 1
    ledger_run_id = run_id or _run_id(ledger_events) or f"runprint-{_event_id_part(clean_action_id)}"

    return [
        LedgerEvent(
            run_id=ledger_run_id,
            sequence=sequence,
            timestamp=event_time,
            type="runprint.recording.completed",
            status="completed",
            message=f"RunPrint recording evidence ingested for `{clean_action_id}`.",
            action_id=clean_action_id,
            details={
                "schema_version": RUNPRINT_INGEST_SCHEMA_VERSION,
                "adapter": "runprint.ingest",
                "recorder": "runprint",
                "target_action_id": clean_action_id,
                "recording_id": clean_recording_id,
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


def build_runprint_ingest_receipt(
    event: LedgerEvent,
    *,
    ledger_source: str,
) -> RunPrintIngestReceipt:
    details = event.details
    return RunPrintIngestReceipt(
        schema_version=RUNPRINT_INGEST_SCHEMA_VERSION,
        status=event.status,
        ledger_source=ledger_source,
        action_id=event.action_id or "unknown",
        recording_id=_string_value(details.get("recording_id"), default="unknown"),
        evidence_bundle_id=_string_value(details.get("evidence_bundle_id"), default="unknown"),
        artifact_count=int(details.get("artifact_count")) if isinstance(details.get("artifact_count"), int) else 0,
        source=_string_value(details.get("source"), default="unknown"),
        summary=_string_value(details.get("summary")),
        event_type=event.type,
        message=event.message,
        next_action="Run `delegation agent-audit --ledger LEDGER` and `delegation approval-inbox --ledger LEDGER` to verify recorded evidence.",
    )


def render_runprint_ingest_receipt(receipt: RunPrintIngestReceipt) -> str:
    lines = [
        "RunPrint Recording Ingest",
        "",
        f"Status: {receipt.status}",
        f"Ledger: {receipt.ledger_source}",
        f"Action: {receipt.action_id}",
        f"Recording: {receipt.recording_id}",
        f"Bundle: {receipt.evidence_bundle_id}",
        f"Artifacts: {receipt.artifact_count}",
        f"Source: {receipt.source}",
    ]
    if receipt.summary:
        lines.append(f"Summary: {receipt.summary}")
    lines.extend(["", receipt.message, "", "Next:", f"- {receipt.next_action}"])
    return "\n".join(lines)


def _artifacts_from_bundle(bundle: JsonMap) -> tuple[RunPrintArtifact, ...]:
    raw = bundle.get("artifacts")
    if not isinstance(raw, list):
        evidence_bundle = bundle.get("evidence_bundle") if isinstance(bundle.get("evidence_bundle"), dict) else {}
        raw = evidence_bundle.get("artifact_manifest")
    if not isinstance(raw, list):
        raw = bundle.get("artifact_manifest")
    if not isinstance(raw, list):
        return ()

    artifacts: list[RunPrintArtifact] = []
    for index, item in enumerate(raw, start=1):
        if isinstance(item, dict):
            artifact_id = _string_value(item.get("id") or item.get("name") or item.get("path"), default=f"artifact-{index}")
            artifacts.append(
                RunPrintArtifact(
                    id=artifact_id,
                    kind=_string_value(item.get("kind") or item.get("type"), default="artifact"),
                    path=_string_value(item.get("path") or item.get("url"), default=artifact_id),
                    required=bool(item.get("required", True)),
                )
            )
        elif isinstance(item, str) and item.strip():
            artifact_id = Path(item).name or f"artifact-{index}"
            artifacts.append(RunPrintArtifact(id=artifact_id, kind="artifact", path=item.strip(), required=True))
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


def _string_value(value: T.Any, *, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
