#!/usr/bin/env python3
"""Summarize planned evidence bundles from a DelegationHQ run ledger."""

from __future__ import annotations

import typing as T
from dataclasses import dataclass


JsonMap = dict[str, T.Any]
RUNPRINT_ADAPTER_ID = "runprint.recorder"


@dataclass(frozen=True)
class EvidenceArtifact:
    id: str
    kind: str
    path: str
    required: bool

    def to_dict(self) -> JsonMap:
        return {
            "id": self.id,
            "kind": self.kind,
            "path": self.path,
            "required": self.required,
        }


@dataclass(frozen=True)
class EvidenceBundlePlan:
    action_id: str
    status: str
    event_type: str
    recording_id: str
    evidence_bundle_id: str
    workspace: str
    scope: str
    artifacts: tuple[EvidenceArtifact, ...]

    def to_dict(self) -> JsonMap:
        return {
            "action_id": self.action_id,
            "status": self.status,
            "event_type": self.event_type,
            "recording_id": self.recording_id,
            "evidence_bundle_id": self.evidence_bundle_id,
            "workspace": self.workspace,
            "scope": self.scope,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }


@dataclass(frozen=True)
class EvidenceRecording:
    action_id: str
    status: str
    event_type: str
    evidence_tool: str
    recording_id: str
    evidence_bundle_id: str
    artifact_count: int
    source: str
    summary: str

    def to_dict(self) -> JsonMap:
        return {
            "action_id": self.action_id,
            "status": self.status,
            "event_type": self.event_type,
            "evidence_tool": self.evidence_tool,
            "recording_id": self.recording_id,
            "evidence_bundle_id": self.evidence_bundle_id,
            "artifact_count": self.artifact_count,
            "source": self.source,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class EvidenceReport:
    source: str
    bundle_plans: tuple[EvidenceBundlePlan, ...]
    recordings: tuple[EvidenceRecording, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def bundle_count(self) -> int:
        return len(self.bundle_plans)

    @property
    def recorded_count(self) -> int:
        return len(self.recordings)

    def to_dict(self) -> JsonMap:
        return {
            "source": self.source,
            "bundle_count": self.bundle_count,
            "recorded_count": self.recorded_count,
            "bundle_plans": [plan.to_dict() for plan in self.bundle_plans],
            "recordings": [recording.to_dict() for recording in self.recordings],
            "warnings": list(self.warnings),
        }


def build_evidence_report(events: T.Sequence[JsonMap], *, source: str = "<memory>") -> EvidenceReport:
    plans: list[EvidenceBundlePlan] = []
    recordings: list[EvidenceRecording] = []
    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()
    seen_recordings: set[tuple[str, str, str]] = set()

    for event in events:
        plan = _bundle_plan_from_event(event, warnings)
        if plan is not None:
            identity = (plan.action_id, plan.evidence_bundle_id)
            if identity not in seen:
                seen.add(identity)
                plans.append(plan)

        recording = _recording_from_event(event)
        if recording is not None:
            identity = (recording.action_id, recording.evidence_tool, recording.recording_id)
            if identity not in seen_recordings:
                seen_recordings.add(identity)
                recordings.append(recording)

    return EvidenceReport(source=source, bundle_plans=tuple(plans), recordings=tuple(recordings), warnings=tuple(warnings))


def render_evidence_report(report: EvidenceReport) -> str:
    lines = [
        "Evidence Bundle Report",
        "",
        f"Source: {report.source}",
        f"Bundles: {report.bundle_count}",
        f"Recorded: {report.recorded_count}",
    ]

    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)

    lines.extend(["", "Recorded evidence:"])
    if not report.recordings:
        lines.append("- none")
    for recording in report.recordings:
        lines.append(f"- {recording.action_id} [{recording.status}]")
        lines.append(f"  tool: {recording.evidence_tool}")
        lines.append(f"  recording_id: {recording.recording_id}")
        lines.append(f"  evidence_bundle_id: {recording.evidence_bundle_id}")
        lines.append(f"  artifacts: {recording.artifact_count}")
        if recording.summary:
            lines.append(f"  summary: {recording.summary}")

    lines.extend(["", "Planned bundles:"])
    if not report.bundle_plans:
        lines.append("- none")
        if report.recordings:
            return "\n".join(lines)
        lines.extend(
            [
                "",
                "Next:",
                "Add a recorder/evidence executor, then rerun `delegation plan ... --ledger ...`.",
            ]
        )
        return "\n".join(lines)

    for plan in report.bundle_plans:
        lines.append(f"- {plan.action_id} [{plan.status}]")
        lines.append(f"  recording_id: {plan.recording_id}")
        lines.append(f"  evidence_bundle_id: {plan.evidence_bundle_id}")
        lines.append(f"  workspace: {plan.workspace}")
        lines.append(f"  scope: {plan.scope}")
        lines.append(f"  artifacts: {len(plan.artifacts)}")
        for artifact in plan.artifacts:
            requirement = "required" if artifact.required else "optional"
            lines.append(f"    - {artifact.id} ({artifact.kind}) {artifact.path} [{requirement}]")

    return "\n".join(lines)


def _bundle_plan_from_event(event: JsonMap, warnings: list[str]) -> EvidenceBundlePlan | None:
    details = _details(event)
    adapter_result = details.get("adapter_result")
    if not isinstance(adapter_result, dict):
        return None
    if _event_adapter(event, adapter_result) != RUNPRINT_ADAPTER_ID:
        return None

    outputs = adapter_result.get("outputs") if isinstance(adapter_result.get("outputs"), dict) else {}
    evidence = adapter_result.get("evidence") if isinstance(adapter_result.get("evidence"), dict) else {}
    session = outputs.get("recording_session") if isinstance(outputs.get("recording_session"), dict) else {}
    bundle = outputs.get("evidence_bundle") if isinstance(outputs.get("evidence_bundle"), dict) else {}

    action_id = _event_action_id(event) or str(adapter_result.get("action_id") or "unknown")
    recording_id = _string_value(evidence.get("recording_id") or session.get("recording_id"))
    evidence_bundle_id = _string_value(evidence.get("evidence_bundle_id") or bundle.get("evidence_bundle_id"))
    if not recording_id or not evidence_bundle_id:
        warnings.append(f"Recorder event `{action_id}` is missing recording or bundle evidence.")
        return None

    manifest_value = evidence.get("artifact_manifest") or bundle.get("artifact_manifest")
    artifacts = _artifact_manifest(manifest_value)
    if not artifacts:
        warnings.append(f"Recorder event `{action_id}` has no artifact manifest.")

    return EvidenceBundlePlan(
        action_id=action_id,
        status=str(adapter_result.get("status") or _event_status(event)),
        event_type=_event_type(event),
        recording_id=recording_id,
        evidence_bundle_id=evidence_bundle_id,
        workspace=_string_value(session.get("workspace"), default="unknown-workspace"),
        scope=_string_value(session.get("scope"), default="unknown scope"),
        artifacts=artifacts,
    )


def _recording_from_event(event: JsonMap) -> EvidenceRecording | None:
    event_type = _event_type(event)
    status = _event_status(event)
    if not (event_type.startswith("runprint.recording.") or event_type.startswith("evidence.recording.")):
        return None
    if event_type.endswith(".planned") or status == "planned":
        return None

    details = _details(event)
    action_id = _string_value(
        details.get("target_action_id")
        or details.get("gate_action_id")
        or event.get("action_id"),
        default="unknown-action",
    )
    evidence_tool = _string_value(
        details.get("evidence_tool")
        or details.get("recorder")
        or ("runprint" if event_type.startswith("runprint.") else "unknown"),
        default="unknown",
    )
    recording_id = _string_value(details.get("evidence_recording_id") or details.get("recording_id"), default="unknown")
    evidence_bundle_id = _string_value(details.get("evidence_bundle_id") or details.get("bundle_id"), default="unknown")
    artifact_count = details.get("artifact_count")
    if not isinstance(artifact_count, int):
        artifacts = details.get("artifact_manifest")
        artifact_count = len(artifacts) if isinstance(artifacts, list) else 0
    return EvidenceRecording(
        action_id=action_id,
        status=status,
        event_type=event_type,
        evidence_tool=evidence_tool,
        recording_id=recording_id,
        evidence_bundle_id=evidence_bundle_id,
        artifact_count=artifact_count,
        source=_string_value(details.get("source"), default="unknown"),
        summary=_string_value(details.get("summary") or event.get("message")),
    )


def _artifact_manifest(value: T.Any) -> tuple[EvidenceArtifact, ...]:
    if not isinstance(value, list):
        return ()
    artifacts: list[EvidenceArtifact] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            artifact_id = _string_value(item.get("id") or item.get("path"), default=f"artifact-{index}")
            artifacts.append(
                EvidenceArtifact(
                    id=artifact_id,
                    kind=_string_value(item.get("kind"), default="artifact"),
                    path=_string_value(item.get("path"), default=artifact_id),
                    required=bool(item.get("required", True)),
                )
            )
        else:
            artifact_id = str(item)
            artifacts.append(EvidenceArtifact(id=artifact_id, kind="artifact", path=artifact_id, required=True))
    return tuple(artifacts)


def _details(event: JsonMap) -> JsonMap:
    return event.get("details") if isinstance(event.get("details"), dict) else {}


def _event_adapter(event: JsonMap, adapter_result: JsonMap) -> str | None:
    details = _details(event)
    adapter = details.get("adapter")
    if isinstance(adapter, str) and adapter.strip():
        return adapter
    result_adapter = adapter_result.get("adapter_id")
    if isinstance(result_adapter, str) and result_adapter.strip():
        return result_adapter
    action = details.get("action") if isinstance(details.get("action"), dict) else {}
    action_adapter = action.get("adapter")
    if isinstance(action_adapter, str) and action_adapter.strip():
        return action_adapter
    return None


def _event_action_id(event: JsonMap) -> str | None:
    value = event.get("action_id")
    return value if isinstance(value, str) and value.strip() else None


def _event_type(event: JsonMap) -> str:
    value = event.get("type")
    return value if isinstance(value, str) and value.strip() else "unknown"


def _event_status(event: JsonMap) -> str:
    value = event.get("status")
    return value if isinstance(value, str) and value.strip() else "unknown"


def _string_value(value: T.Any, *, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
