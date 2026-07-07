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
class EvidenceReport:
    source: str
    bundle_plans: tuple[EvidenceBundlePlan, ...]
    warnings: tuple[str, ...] = ()

    @property
    def bundle_count(self) -> int:
        return len(self.bundle_plans)

    def to_dict(self) -> JsonMap:
        return {
            "source": self.source,
            "bundle_count": self.bundle_count,
            "bundle_plans": [plan.to_dict() for plan in self.bundle_plans],
            "warnings": list(self.warnings),
        }


def build_evidence_report(events: T.Sequence[JsonMap], *, source: str = "<memory>") -> EvidenceReport:
    plans: list[EvidenceBundlePlan] = []
    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()

    for event in events:
        plan = _bundle_plan_from_event(event, warnings)
        if plan is None:
            continue
        identity = (plan.action_id, plan.evidence_bundle_id)
        if identity in seen:
            continue
        seen.add(identity)
        plans.append(plan)

    return EvidenceReport(source=source, bundle_plans=tuple(plans), warnings=tuple(warnings))


def render_evidence_report(report: EvidenceReport) -> str:
    lines = [
        "Evidence Bundle Report",
        "",
        f"Source: {report.source}",
        f"Bundles: {report.bundle_count}",
    ]

    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)

    lines.extend(["", "Planned bundles:"])
    if not report.bundle_plans:
        lines.append("- none")
        lines.extend(
            [
                "",
                "Next:",
                "Add a `runprint.recorder` executor, then rerun `delegation plan ... --ledger ...`.",
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
