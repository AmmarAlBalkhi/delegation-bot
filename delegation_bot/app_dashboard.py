#!/usr/bin/env python3
"""One-screen app dashboard bundle for DelegationHQ."""

from __future__ import annotations

import typing as T
from dataclasses import dataclass
from pathlib import Path

from delegation_bot.app_state import AppState, build_app_state
from delegation_bot.approval_preview import ApprovalPreviewReport, build_approval_preview_report
from delegation_bot.mission_timeline import MissionTimelineReport, build_timeline_report_from_paths


JsonMap = dict[str, T.Any]
APP_DASHBOARD_SCHEMA_VERSION = "delegation.app-dashboard.v1"


@dataclass(frozen=True)
class AppDashboardReport:
    schema_version: str
    status: str
    workspace: str
    state: AppState
    timeline: MissionTimelineReport
    approval_preview: ApprovalPreviewReport | None
    command_center: tuple[JsonMap, ...]
    warnings: tuple[str, ...] = ()

    @property
    def next_actions(self) -> tuple[str, ...]:
        actions: list[str] = []
        actions.extend(_command_values(self.command_center))
        actions.extend(self.state.next_actions[:4])
        actions.append(self.timeline.next_action)
        return tuple(_dedupe(actions))

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "workspace": self.workspace,
            "state": self.state.to_dict(),
            "timeline": self.timeline.to_dict(),
            "approval_preview": self.approval_preview.to_dict() if self.approval_preview else None,
            "command_center": list(self.command_center),
            "warnings": list(self.warnings),
            "next_actions": list(self.next_actions),
        }


def build_app_dashboard_report(
    *,
    workspace_root: Path,
    preview_agent: str | None = None,
    preview_action: str = "read.workspace",
    preview_target: str = "workspace",
    preview_risk: str | None = None,
) -> AppDashboardReport:
    """Build the functional local app bundle for one workspace."""

    workspace = workspace_root.resolve()
    state = build_app_state(workspace_root=workspace)
    state_data = state.to_dict()
    timeline = build_timeline_report_from_paths(workspace_root=workspace)
    preview = _build_preview(
        state_data,
        workspace_root=workspace,
        preview_agent=preview_agent,
        preview_action=preview_action,
        preview_target=preview_target,
        preview_risk=preview_risk,
    )
    return AppDashboardReport(
        schema_version=APP_DASHBOARD_SCHEMA_VERSION,
        status=_dashboard_status(state.status, timeline.status, preview),
        workspace=str(workspace),
        state=state,
        timeline=timeline,
        approval_preview=preview,
        command_center=tuple(_command_center(workspace, state_data, timeline, preview)),
        warnings=tuple(_dashboard_warnings(state_data, timeline, preview)),
    )


def render_app_dashboard_report(report: AppDashboardReport) -> str:
    state_data = report.state.to_dict()
    workspace = state_data.get("workspace") if isinstance(state_data.get("workspace"), dict) else {}
    ledger = state_data.get("ledger") if isinstance(state_data.get("ledger"), dict) else {}
    agents = state_data.get("agents") if isinstance(state_data.get("agents"), dict) else {}
    preview = report.approval_preview
    lines = [
        "DelegationHQ App Dashboard",
        "",
        f"Status: {report.status}",
        f"Workspace: {report.workspace}",
        f"Ledger: {ledger.get('status', 'unknown')} ({ledger.get('event_count', 0)} events)",
        f"Timeline: {report.timeline.status} ({report.timeline.shown_count} shown)",
        f"Agents: {agents.get('passport_count', 0)}",
    ]
    if workspace:
        lines.append(f"GitHub required: {str(False).lower()}")
    if preview:
        lines.extend(
            [
                "",
                "Current request:",
                f"- agent: {preview.agent_id}",
                f"- action: {preview.action}",
                f"- target: {preview.target}",
                f"- decision: {preview.gate.decision}",
                f"- risk: {preview.gate.effective_risk}",
            ]
        )

    lines.extend(["", "Command center:"])
    for command in report.command_center:
        label = command.get("label", "command")
        value = command.get("command", "")
        purpose = command.get("purpose", "")
        lines.append(f"- {label}: {value}")
        if purpose:
            lines.append(f"  {purpose}")

    lines.extend(["", "Timeline:"])
    if report.timeline.items:
        for item in report.timeline.items[-8:]:
            sequence = f"{item.sequence}. " if item.sequence is not None else "- "
            attention = " needs-attention" if item.needs_attention else ""
            lines.append(f"{sequence}[{item.stage}] {item.status} {item.title}{attention}")
    else:
        lines.append("- none")

    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)

    lines.extend(
        [
            "",
            "Plain language:",
            "- This is the app brain: workspace, agents, approval request, timeline, and safe commands together.",
            "- The visual design can change later without changing this control data.",
            "",
            "Next:",
        ]
    )
    lines.extend(f"- {action}" for action in report.next_actions[:8])
    return "\n".join(lines)


def _build_preview(
    state_data: JsonMap,
    *,
    workspace_root: Path,
    preview_agent: str | None,
    preview_action: str,
    preview_target: str,
    preview_risk: str | None,
) -> ApprovalPreviewReport | None:
    agent_id = preview_agent or _first_agent_id(state_data)
    if not agent_id:
        return None
    return build_approval_preview_report(
        agent_id=agent_id,
        action=preview_action,
        target=preview_target,
        workspace_root=workspace_root,
        requested_risk=preview_risk,
    )


def _dashboard_status(state_status: str, timeline_status: str, preview: ApprovalPreviewReport | None) -> str:
    if state_status == "blocked" or timeline_status == "blocked" or (preview and preview.gate.decision == "block"):
        return "blocked"
    if (
        state_status == "needs_attention"
        or timeline_status == "needs_attention"
        or (preview and preview.gate.decision in {"approval_required", "warn"})
    ):
        return "needs_attention"
    if timeline_status in {"recorded", "approved", "gated"}:
        return timeline_status
    return state_status


def _command_center(
    workspace: Path,
    state_data: JsonMap,
    timeline: MissionTimelineReport,
    preview: ApprovalPreviewReport | None,
) -> T.Iterator[JsonMap]:
    yield {
        "id": "refresh_dashboard",
        "label": "Refresh dashboard",
        "command": f"delegation app-dashboard --workspace {workspace}",
        "purpose": "Reload the one-screen control plane state.",
        "risk": "none",
    }
    if preview:
        yield {
            "id": "preview_request",
            "label": "Preview request",
            "command": f"delegation approval-preview {preview.agent_id} --workspace {workspace} --action {preview.action} --target {preview.target}",
            "purpose": "Recheck the agent passport before action.",
            "risk": preview.gate.effective_risk,
        }
        if preview.gate.decision == "allow":
            yield {
                "id": "execute_agent",
                "label": "Execute under control",
                "command": f"delegation agent-run {preview.agent_id} --workspace {workspace} --action {preview.action} --target {preview.target} --execute --confirm LOCAL_AGENT_EXECUTION",
                "purpose": "Run only after Agent Gate allows it and exact confirmation is present.",
                "risk": preview.gate.effective_risk,
            }
        if preview.gate.decision == "approval_required" and preview.ledger:
            yield {
                "id": "approve_request",
                "label": "Record approval",
                "command": f"delegation approval-decision --ledger {preview.ledger} --action-id {preview.action_id} --decision approve --approver YOUR_NAME",
                "purpose": "Attach human approval evidence before live action.",
                "risk": preview.gate.effective_risk,
            }
            yield {
                "id": "block_request",
                "label": "Block request",
                "command": f"delegation approval-decision --ledger {preview.ledger} --action-id {preview.action_id} --decision block --approver YOUR_NAME",
                "purpose": "Stop this request and keep a human decision receipt.",
                "risk": preview.gate.effective_risk,
            }
    ledger = state_data.get("ledger") if isinstance(state_data.get("ledger"), dict) else {}
    ledger_path = ledger.get("path")
    if isinstance(ledger_path, str) and ledger_path:
        yield {
            "id": "timeline",
            "label": "Review timeline",
            "command": f"delegation timeline --ledger {ledger_path}",
            "purpose": timeline.next_action,
            "risk": "none",
        }


def _dashboard_warnings(
    state_data: JsonMap,
    timeline: MissionTimelineReport,
    preview: ApprovalPreviewReport | None,
) -> T.Iterator[str]:
    ledger = state_data.get("ledger") if isinstance(state_data.get("ledger"), dict) else {}
    for warning in ledger.get("warnings", []) if isinstance(ledger.get("warnings"), list) else []:
        yield str(warning)
    for warning in timeline.warnings:
        yield warning
    if preview is None:
        yield "No agent passport is available for an approval preview."
    elif preview.warnings:
        yield from preview.warnings


def _first_agent_id(state_data: JsonMap) -> str | None:
    agents = state_data.get("agents") if isinstance(state_data.get("agents"), dict) else {}
    passports = agents.get("passports") if isinstance(agents.get("passports"), list) else []
    for passport in passports:
        if isinstance(passport, dict) and isinstance(passport.get("id"), str) and passport["id"].strip():
            return passport["id"].strip()
    return None


def _command_values(commands: T.Iterable[JsonMap]) -> T.Iterator[str]:
    for command in commands:
        value = command.get("command")
        if isinstance(value, str) and value.strip():
            yield value


def _dedupe(values: T.Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
