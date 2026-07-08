#!/usr/bin/env python3
"""App-ready local state for the future DelegationHQ cockpit."""

from __future__ import annotations

import typing as T
from dataclasses import dataclass, field
from pathlib import Path

from delegation_bot import __version__
from delegation_bot.agent_gate import build_agent_gate_audit_report, build_agent_gate_report
from delegation_bot.agent_passports import build_agent_passport_report
from delegation_bot.app_plan import build_app_plan
from delegation_bot.approval_inbox import build_approval_inbox_report
from delegation_bot.dashboard import build_dashboard_snapshot
from delegation_bot.doctor import DoctorReport, run_doctor
from delegation_bot.evidence_report import build_evidence_report
from delegation_bot.harness_manifest import Manifest, ManifestError, load_manifest, validate_manifest
from delegation_bot.ledger import LedgerError, load_ledger_events
from delegation_bot.local_workspace import (
    DEFAULT_WORKSPACE_AGENT_RUN_LEDGER,
    WorkspaceStatusReport,
    build_workspace_status,
)
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
    agent_audit: JsonMap | None = None
    approval_inbox: JsonMap | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> JsonMap:
        return {
            "path": self.path,
            "status": self.status,
            "event_count": self.event_count,
            "dashboard": self.dashboard,
            "evidence": self.evidence,
            "agent_audit": self.agent_audit,
            "approval_inbox": self.approval_inbox,
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
    agents: JsonMap
    agent_gate: JsonMap
    ledger: AppStateLedger
    workspace: JsonMap | None
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
            "agents": self.agents,
            "agent_gate": self.agent_gate,
            "ledger": self.ledger.to_dict(),
            "workspace": self.workspace,
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
    workspace_root: Path | None = None,
    agent_registries: T.Sequence[Path] = (),
    gate_agent: str | None = None,
    gate_action: str | None = None,
    gate_target: str | None = None,
    gate_risk: str | None = None,
    gate_approvals: T.Sequence[str] = (),
    gate_evidence: T.Sequence[str] = (),
) -> AppState:
    """Build a read-only state bundle for the future local app."""

    workspace_report = build_workspace_status(root=workspace_root) if workspace_root else None
    workspace_registry = Path(workspace_report.registry) if workspace_report and Path(workspace_report.registry).exists() else None
    workspace_harnessfile = (
        Path(workspace_report.harnessfile) if workspace_report and Path(workspace_report.harnessfile).exists() else None
    )
    workspace_agent_ledger = workspace_root.resolve() / DEFAULT_WORKSPACE_AGENT_RUN_LEDGER if workspace_root else None

    if harnessfile is None and workspace_harnessfile is not None:
        harnessfile = workspace_harnessfile
    if ledger_path is None and workspace_report is not None:
        ledger_path = workspace_agent_ledger if workspace_agent_ledger and workspace_agent_ledger.exists() else Path(workspace_report.ledger)

    resolved_agent_registries = list(agent_registries)
    if workspace_registry is not None and workspace_registry not in resolved_agent_registries:
        resolved_agent_registries.append(workspace_registry)

    app_plan = build_app_plan()
    doctor = run_doctor(root, include_github=include_github, include_github_app=include_github_app)
    release = build_release_readiness_report(root, strict_artifacts=strict_artifacts)
    manifest, manifest_warnings = _load_optional_manifest(harnessfile)
    ledger = _build_ledger_state(
        ledger_path=ledger_path,
        manifest=manifest,
        manifest_warnings=manifest_warnings,
    )
    agents = build_agent_passport_report(
        manifest=manifest,
        manifest_source=str(harnessfile) if harnessfile else None,
        registry_paths=resolved_agent_registries,
    )
    agent_gate = _build_agent_gate_state(
        manifest=manifest,
        harnessfile=harnessfile,
        registry_paths=resolved_agent_registries,
        agent_id=gate_agent,
        action=gate_action,
        target=gate_target,
        risk=gate_risk,
        approvals=gate_approvals,
        evidence=gate_evidence,
    )

    return AppState(
        schema_version="delegation.app-state.v1",
        app_name=app_plan.app_name,
        version=__version__,
        mode="local-read-only",
        status=_overall_status(doctor, release, ledger, agents.to_dict(), agent_gate, workspace_report),
        read_only=True,
        live_risk="none",
        doctor=doctor.to_dict(),
        release=release.to_dict(),
        app_plan=app_plan.to_dict(),
        agents=agents.to_dict(),
        agent_gate=agent_gate,
        ledger=ledger,
        workspace=workspace_report.to_dict() if workspace_report else None,
        next_actions=_next_actions(doctor, release, ledger, workspace_report),
        guardrails=(
            "This state command is read-only.",
            "It does not call models, run agents, write to GitHub, or dispatch workflows.",
            "A workspace can run fully local; GitHub is an adapter, not the core.",
            "Live actions still require their dedicated apply commands and exact confirmations.",
            *app_plan.guardrails,
        ),
    )


def render_app_state(state: AppState) -> str:
    dashboard = state.ledger.dashboard or {}
    dashboard_counts = dashboard.get("counts") if isinstance(dashboard.get("counts"), dict) else {}
    mission = dashboard.get("mission") if isinstance(dashboard.get("mission"), dict) else {}
    evidence = state.ledger.evidence or {}
    agent_audit = state.ledger.agent_audit or {}
    approval_inbox = state.ledger.approval_inbox or {}
    agents = state.agents
    agent_gate = state.agent_gate
    workspace = state.workspace

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
        f"- Agent passports: {agents.get('status', 'unknown')} ({agents.get('passport_count', 0)} agents)",
        f"- Agent gate: {agent_gate.get('status', 'unknown')}",
        f"- Ledger: {state.ledger.status} ({state.ledger.event_count} events)",
    ]

    if workspace:
        lines.extend(
            [
                "",
                "Workspace:",
                f"- status: {workspace.get('status', 'unknown')}",
                f"- root: {workspace.get('root', 'unknown')}",
                f"- harness: {workspace.get('harness_status', 'unknown')}",
                f"- registry: {workspace.get('registry_status', 'unknown')}",
                f"- agents: {workspace.get('agent_count', 0)}",
                "- GitHub required: false",
            ]
        )

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
    if agent_audit:
        lines.append(f"- agent audit: {agent_audit.get('status', 'unknown')}")
    if approval_inbox:
        lines.append(
            f"- approval inbox: {approval_inbox.get('status', 'unknown')} "
            f"({approval_inbox.get('pending_count', 0)} pending)"
        )

    warnings = list(state.ledger.warnings)
    if warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in warnings)

    lines.extend(["", "Next:"])
    lines.extend(f"- {action}" for action in state.next_actions)

    lines.extend(["", "Guardrails:"])
    lines.extend(f"- {guardrail}" for guardrail in state.guardrails[:4])
    return "\n".join(lines)


def _build_ledger_state(
    *,
    ledger_path: Path | None,
    manifest: Manifest | None,
    manifest_warnings: T.Sequence[str],
) -> AppStateLedger:
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

    dashboard = build_dashboard_snapshot(events, manifest=manifest, source=str(path))
    evidence = build_evidence_report(events, source=str(path))
    agent_audit = build_agent_gate_audit_report(events, ledger_source=str(path))
    approval_inbox = build_approval_inbox_report(events, ledger_source=str(path))
    audit_warnings = agent_audit.warnings if agent_audit.gate_count else ()
    inbox_warnings = approval_inbox.warnings if approval_inbox.item_count else ()
    return AppStateLedger(
        path=str(path),
        status=dashboard.status,
        event_count=len(events),
        dashboard=dashboard.to_dict(),
        evidence=evidence.to_dict(),
        agent_audit=agent_audit.to_dict(),
        approval_inbox=approval_inbox.to_dict(),
        warnings=tuple([*manifest_warnings, *dashboard.warnings, *evidence.warnings, *audit_warnings, *inbox_warnings]),
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


def _overall_status(
    doctor: DoctorReport,
    release: ReleaseReadinessReport,
    ledger: AppStateLedger,
    agents: JsonMap,
    agent_gate: JsonMap,
    workspace: WorkspaceStatusReport | None = None,
) -> str:
    approval_inbox = ledger.approval_inbox or {}
    if doctor.failed_count:
        return "blocked"
    if (
        release.failed_count
        or ledger.status in {"failed", "blocked", "needs_attention", "error"}
        or approval_inbox.get("status") in {"needs_attention", "blocked"}
        or agents.get("status") == "warning"
        or agent_gate.get("status") in {"blocked", "incomplete"}
        or (workspace is not None and workspace.status in {"missing", "needs_attention"})
    ):
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
    workspace: WorkspaceStatusReport | None = None,
) -> tuple[str, ...]:
    actions: list[str] = []
    if doctor.failed_count:
        actions.extend(doctor.next_commands[:2])
    if workspace is not None:
        actions.extend(workspace.next_actions[:2])
        actions.append(f"delegation agent-run AGENT_ID --workspace {workspace.root} --execute --confirm LOCAL_AGENT_EXECUTION")
        actions.append(f"delegation cockpit --workspace {workspace.root}")
    if ledger.status in {"not_loaded", "missing", "error"}:
        actions.append("delegation demo --ledger .delegation/demo.jsonl")
    elif ledger.dashboard:
        next_safe_action = ledger.dashboard.get("next_safe_action")
        if isinstance(next_safe_action, str) and next_safe_action.strip():
            actions.append(next_safe_action)
    if release.failed_count or release.warning_count:
        actions.extend(release.next_commands[:2])
    if workspace is not None:
        actions.append(f"delegation app-state --workspace {workspace.root} --json")
    else:
        actions.append("delegation app-state --ledger .delegation/demo.jsonl --json")
    return tuple(_dedupe(actions))


def _build_agent_gate_state(
    *,
    manifest: Manifest | None,
    harnessfile: Path | None,
    registry_paths: T.Sequence[Path],
    agent_id: str | None,
    action: str | None,
    target: str | None,
    risk: str | None,
    approvals: T.Sequence[str],
    evidence: T.Sequence[str],
) -> JsonMap:
    if not any((agent_id, action, target)):
        return {
            "status": "not_requested",
            "preview_count": 0,
            "next_command": "delegation agent-gate Harnessfile.yaml AGENT_ID --action ACTION --target TARGET",
        }

    missing = [
        name
        for name, value in (
            ("agent id", agent_id),
            ("action", action),
            ("target", target),
        )
        if not value
    ]
    if missing:
        return {
            "status": "incomplete",
            "preview_count": 0,
            "warnings": ["Agent Gate request is missing: " + ", ".join(missing) + "."],
            "next_command": "Provide --gate-agent, --gate-action, and --gate-target together.",
        }

    report = build_agent_gate_report(
        agent_id=agent_id or "",
        action=action or "",
        target=target or "",
        manifest=manifest,
        manifest_source=str(harnessfile) if harnessfile else None,
        registry_paths=registry_paths,
        requested_risk=risk,
        provided_approvals=approvals,
        provided_evidence=evidence,
    )
    data = report.to_dict()
    data["preview_count"] = 1
    return data


def _dedupe(values: T.Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
