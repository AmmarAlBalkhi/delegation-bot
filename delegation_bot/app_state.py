#!/usr/bin/env python3
"""App-ready local state for the future DelegationHQ cockpit."""

from __future__ import annotations

import typing as T
from dataclasses import dataclass, field
from pathlib import Path

from delegation_bot import __version__
from delegation_bot.app_plan import build_app_plan
from delegation_bot.dashboard import build_dashboard_snapshot
from delegation_bot.doctor import DoctorReport, run_doctor
from delegation_bot.evidence_report import build_evidence_report
from delegation_bot.harness_manifest import Manifest, ManifestError, load_manifest, validate_manifest
from delegation_bot.ledger import LedgerError, load_ledger_events
from delegation_bot.release_readiness import ReleaseReadinessReport, build_release_readiness_report


ROOT = Path(__file__).resolve().parents[1]
JsonMap = dict[str, T.Any]


@dataclass(frozen=True)
class AppStateLedger:
    path: str | None
    status: str
    event_count: int = 0
    dashboard: JsonMap | None = None
    evidence: JsonMap | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> JsonMap:
        return {
            "path": self.path,
            "status": self.status,
            "event_count": self.event_count,
            "dashboard": self.dashboard,
            "evidence": self.evidence,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class AppState:
    schema_version: str
    app_name: str
    version: str
    mode: str
    status: str
    read_only: bool
    live_risk: str
    doctor: JsonMap
    release: JsonMap
    app_plan: JsonMap
    ledger: AppStateLedger
    next_actions: tuple[str, ...]
    guardrails: tuple[str, ...]

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "app_name": self.app_name,
            "version": self.version,
            "mode": self.mode,
            "status": self.status,
            "read_only": self.read_only,
            "live_risk": self.live_risk,
            "doctor": self.doctor,
            "release": self.release,
            "app_plan": self.app_plan,
            "ledger": self.ledger.to_dict(),
            "next_actions": list(self.next_actions),
            "guardrails": list(self.guardrails),
        }


def build_app_state(
    root: Path = ROOT,
    *,
    ledger_path: Path | None = None,
    harnessfile: Path | None = None,
    include_github: bool = False,
    include_github_app: bool = False,
    strict_artifacts: bool = False,
) -> AppState:
    """Build a read-only state bundle for the future local app."""

    app_plan = build_app_plan()
    doctor = run_doctor(root, include_github=include_github, include_github_app=include_github_app)
    release = build_release_readiness_report(root, strict_artifacts=strict_artifacts)
    ledger = _build_ledger_state(ledger_path=ledger_path, harnessfile=harnessfile)

    return AppState(
        schema_version="delegation.app-state.v1",
        app_name=app_plan.app_name,
        version=__version__,
        mode="local-read-only",
        status=_overall_status(doctor, release, ledger),
        read_only=True,
        live_risk="none",
        doctor=doctor.to_dict(),
        release=release.to_dict(),
        app_plan=app_plan.to_dict(),
        ledger=ledger,
        next_actions=_next_actions(doctor, release, ledger),
        guardrails=(
            "This state command is read-only.",
            "It does not call models, run agents, write to GitHub, or dispatch workflows.",
            "Live actions still require their dedicated apply commands and exact confirmations.",
            *app_plan.guardrails,
        ),
    )


def render_app_state(state: AppState) -> str:
    dashboard = state.ledger.dashboard or {}
    dashboard_counts = dashboard.get("counts") if isinstance(dashboard.get("counts"), dict) else {}
    mission = dashboard.get("mission") if isinstance(dashboard.get("mission"), dict) else {}
    evidence = state.ledger.evidence or {}

    lines = [
        "DelegationHQ App State",
        "",
        f"Status: {state.status}",
        f"App: {state.app_name}",
        f"Version: {state.version}",
        f"Mode: {state.mode}",
        f"Read-only: {str(state.read_only).lower()}",
        f"Live risk: {state.live_risk}",
        "",
        "Health:",
        (
            f"- Doctor: {state.doctor['status']} "
            f"({state.doctor['ready_count']} ready, {state.doctor['failed_count']} failed)"
        ),
        (
            f"- Release: {state.release['status']} "
            f"({state.release['ready_count']} ready, "
            f"{state.release['warning_count']} warnings, {state.release['failed_count']} failed)"
        ),
        f"- Ledger: {state.ledger.status} ({state.ledger.event_count} events)",
    ]

    if mission:
        lines.extend(
            [
                "",
                "Mission:",
                f"- id: {mission.get('id', 'unknown')}",
                f"- objective: {mission.get('objective', 'unknown')}",
                f"- next safe action: {dashboard.get('next_safe_action', 'unknown')}",
            ]
        )

    if dashboard_counts:
        lines.extend(
            [
                "",
                "Snapshot:",
                f"- adapters: {dashboard_counts.get('adapters', 0)}",
                f"- evals: {dashboard_counts.get('evals', 0)}",
                f"- agents: {dashboard_counts.get('agents', 0)}",
                f"- feedback items: {dashboard_counts.get('feedback_items', 0)}",
            ]
        )

    if evidence:
        lines.append(f"- evidence bundles: {evidence.get('bundle_count', 0)}")

    warnings = list(state.ledger.warnings)
    if warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in warnings)

    lines.extend(["", "Next:"])
    lines.extend(f"- {action}" for action in state.next_actions)

    lines.extend(["", "Guardrails:"])
    lines.extend(f"- {guardrail}" for guardrail in state.guardrails[:4])
    return "\n".join(lines)


def _build_ledger_state(*, ledger_path: Path | None, harnessfile: Path | None) -> AppStateLedger:
    if ledger_path is None:
        return AppStateLedger(
            path=None,
            status="not_loaded",
            warnings=("No ledger was provided. Run `delegation demo --ledger .delegation/demo.jsonl`.",),
        )

    path = ledger_path
    if not path.exists():
        return AppStateLedger(
            path=str(path),
            status="missing",
            warnings=(f"Ledger does not exist: {path}",),
        )

    try:
        events = load_ledger_events(path)
    except LedgerError as exc:
        return AppStateLedger(path=str(path), status="error", warnings=(str(exc),))

    manifest, manifest_warnings = _load_optional_manifest(harnessfile)
    dashboard = build_dashboard_snapshot(events, manifest=manifest, source=str(path))
    evidence = build_evidence_report(events, source=str(path))
    return AppStateLedger(
        path=str(path),
        status=dashboard.status,
        event_count=len(events),
        dashboard=dashboard.to_dict(),
        evidence=evidence.to_dict(),
        warnings=tuple([*manifest_warnings, *dashboard.warnings, *evidence.warnings]),
    )


def _load_optional_manifest(path: Path | None) -> tuple[Manifest | None, list[str]]:
    if path is None:
        return None, []
    try:
        manifest = load_manifest(path)
    except (OSError, ManifestError) as exc:
        return None, [f"Harnessfile could not be loaded: {exc}"]
    errors = validate_manifest(manifest)
    if errors:
        return None, [f"Harnessfile is invalid: {error}" for error in errors]
    return manifest, []


def _overall_status(doctor: DoctorReport, release: ReleaseReadinessReport, ledger: AppStateLedger) -> str:
    if doctor.failed_count:
        return "blocked"
    if release.failed_count or ledger.status in {"failed", "blocked", "needs_attention", "error"}:
        return "needs_attention"
    if ledger.status == "missing":
        return "usable"
    if ledger.status == "ready" and release.warning_count == 0:
        return "ready"
    return "usable"


def _next_actions(
    doctor: DoctorReport,
    release: ReleaseReadinessReport,
    ledger: AppStateLedger,
) -> tuple[str, ...]:
    actions: list[str] = []
    if doctor.failed_count:
        actions.extend(doctor.next_commands[:2])
    if ledger.status in {"not_loaded", "missing", "error"}:
        actions.append("delegation demo --ledger .delegation/demo.jsonl")
    elif ledger.dashboard:
        next_safe_action = ledger.dashboard.get("next_safe_action")
        if isinstance(next_safe_action, str) and next_safe_action.strip():
            actions.append(next_safe_action)
    if release.failed_count or release.warning_count:
        actions.extend(release.next_commands[:2])
    actions.append("delegation app-state --ledger .delegation/demo.jsonl --json")
    return tuple(_dedupe(actions))


def _dedupe(values: T.Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
