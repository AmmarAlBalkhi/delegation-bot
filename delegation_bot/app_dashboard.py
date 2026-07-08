#!/usr/bin/env python3
"""One-screen app dashboard bundle for DelegationHQ."""

from __future__ import annotations

import typing as T
from dataclasses import dataclass
from pathlib import Path

from delegation_bot.agent_packet import AgentPacketReport, build_agent_packet_report
from delegation_bot.app_state import AppState, build_app_state
from delegation_bot.approval_preview import ApprovalPreviewReport, build_approval_preview_report
from delegation_bot.ledger import LedgerError, load_ledger_events
from delegation_bot.mission_timeline import MissionTimelineReport, build_timeline_report_from_paths
from delegation_bot.workspace_flow import WorkspaceFlowReport, build_workspace_flow_report


JsonMap = dict[str, T.Any]
APP_DASHBOARD_SCHEMA_VERSION = "delegation.app-dashboard.v1"


@dataclass(frozen=True)
class AppDashboardReport:
    schema_version: str
    status: str
    workspace: str
    state: AppState
    timeline: MissionTimelineReport
    active_request: JsonMap | None
    request_cards: tuple[JsonMap, ...]
    approval_preview: ApprovalPreviewReport | None
    agent_packet: AgentPacketReport | None
    workspace_flow: WorkspaceFlowReport
    product_areas: tuple[JsonMap, ...]
    command_center: tuple[JsonMap, ...]
    control_loop: tuple[JsonMap, ...]
    warnings: tuple[str, ...] = ()

    @property
    def next_actions(self) -> tuple[str, ...]:
        actions: list[str] = []
        actions.append(self.workspace_flow.next_command)
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
            "active_request": self.active_request,
            "request_cards": list(self.request_cards),
            "approval_preview": self.approval_preview.to_dict() if self.approval_preview else None,
            "agent_packet": self.agent_packet.to_dict() if self.agent_packet else None,
            "workspace_flow": self.workspace_flow.to_dict(),
            "product_areas": list(self.product_areas),
            "command_center": list(self.command_center),
            "control_loop": list(self.control_loop),
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
    preview_note: str | None = None,
    preview_expires_at: str | None = None,
) -> AppDashboardReport:
    """Build the functional local app bundle for one workspace."""

    workspace = workspace_root.resolve()
    state = build_app_state(workspace_root=workspace)
    state_data = state.to_dict()
    timeline = build_timeline_report_from_paths(workspace_root=workspace, limit=0)
    request_cards = tuple(_request_cards(state_data))
    active_request = _select_active_request(request_cards)
    preview_seed = _preview_seed(
        active_request,
        preview_agent=preview_agent,
        preview_action=preview_action,
        preview_target=preview_target,
        preview_risk=preview_risk,
    )
    preview = _build_preview(
        state_data,
        workspace_root=workspace,
        preview_agent=preview_seed["agent_id"],
        preview_action=preview_seed["action"],
        preview_target=preview_seed["target"],
        preview_risk=preview_seed["risk"],
        preview_note=preview_note,
        preview_expires_at=preview_expires_at,
    )
    agent_packet = _build_agent_packet(preview)
    workspace_flow = build_workspace_flow_report(workspace_root=workspace, state=state, timeline=timeline)
    command_center = tuple(_command_center(workspace, state_data, timeline, preview, active_request))
    control_loop = tuple(_control_loop(state_data, timeline, preview, agent_packet, command_center))
    return AppDashboardReport(
        schema_version=APP_DASHBOARD_SCHEMA_VERSION,
        status=_dashboard_status(state.status, timeline.status, preview),
        workspace=str(workspace),
        state=state,
        timeline=timeline,
        active_request=active_request,
        request_cards=request_cards,
        approval_preview=preview,
        agent_packet=agent_packet,
        workspace_flow=workspace_flow,
        product_areas=tuple(_product_areas(state_data, timeline, preview, agent_packet, command_center)),
        command_center=command_center,
        control_loop=control_loop,
        warnings=tuple(_dashboard_warnings(state_data, timeline, preview, agent_packet)),
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
    if report.active_request:
        lines.extend(
            [
                "",
                "Active request card:",
                f"- status: {report.active_request.get('status', 'unknown')}",
                f"- summary: {report.active_request.get('request_summary') or report.active_request.get('title', 'unknown')}",
                f"- action id: {report.active_request.get('action_id', 'unknown')}",
            ]
        )
    if report.agent_packet:
        lines.extend(
            [
                "",
                "Agent handoff:",
                f"- packet: {report.agent_packet.status}",
                f"- action: {report.agent_packet.action_id}",
            ]
        )

    lines.extend(["", "Control loop:"])
    lines.append(f"- Workspace flow: {report.workspace_flow.status}")
    lines.append(f"  current step: {report.workspace_flow.current_step}")
    lines.append(f"  next: {report.workspace_flow.next_command}")
    for step in report.control_loop:
        lines.append(f"- {step.get('title', 'Step')}: {step.get('status', 'unknown')}")
        summary = step.get("summary")
        if isinstance(summary, str) and summary:
            lines.append(f"  {summary}")

    lines.extend(["", "Product areas:"])
    for area in report.product_areas:
        lines.append(f"- {area.get('title', 'Area')}: {area.get('status', 'unknown')}")
        summary = area.get("summary")
        if isinstance(summary, str) and summary:
            lines.append(f"  {summary}")

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
            "- This is the app brain for the real trust loop: mission, agents, approvals, evidence, timeline, and settings.",
            "- The visual design can change later without changing this control data.",
            "",
            "Next:",
        ]
    )
    lines.extend(f"- {action}" for action in report.next_actions[:8])
    return "\n".join(lines)


def _request_cards(state_data: JsonMap) -> T.Iterator[JsonMap]:
    ledger = state_data.get("ledger") if isinstance(state_data.get("ledger"), dict) else {}
    inbox = ledger.get("approval_inbox") if isinstance(ledger.get("approval_inbox"), dict) else {}
    items = inbox.get("items") if isinstance(inbox.get("items"), list) else []
    for item in items:
        if isinstance(item, dict):
            yield item


def _select_active_request(cards: T.Sequence[JsonMap]) -> JsonMap | None:
    if not cards:
        return None
    status_order = (
        "pending_approval",
        "warning",
        "approved",
        "needs_evidence",
        "ready_for_recording",
        "blocked_by_human",
        "blocked_by_gate",
        "recorded",
    )
    for status in status_order:
        for card in reversed(cards):
            if card.get("status") == status:
                return card
    return cards[-1]


def _preview_seed(
    active_request: JsonMap | None,
    *,
    preview_agent: str | None,
    preview_action: str,
    preview_target: str,
    preview_risk: str | None,
) -> JsonMap:
    if preview_agent or active_request is None:
        return {
            "agent_id": preview_agent,
            "action": preview_action,
            "target": preview_target,
            "risk": preview_risk,
        }
    return {
        "agent_id": _string(active_request.get("agent_id")) or None,
        "action": _string(active_request.get("action"), default=preview_action),
        "target": _string(active_request.get("target"), default=preview_target),
        "risk": _string(active_request.get("risk")) or preview_risk,
    }


def _build_preview(
    state_data: JsonMap,
    *,
    workspace_root: Path,
    preview_agent: str | None,
    preview_action: str,
    preview_target: str,
    preview_risk: str | None,
    preview_note: str | None,
    preview_expires_at: str | None,
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
        reviewer_note=preview_note,
        expires_at=preview_expires_at,
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


def _build_agent_packet(preview: ApprovalPreviewReport | None) -> AgentPacketReport | None:
    if preview is None or not preview.ledger:
        return None
    ledger_path = Path(preview.ledger)
    if not ledger_path.exists():
        return build_agent_packet_report((), action_id=preview.action_id, ledger_source=str(ledger_path))
    try:
        events = load_ledger_events(ledger_path)
    except LedgerError:
        return build_agent_packet_report((), action_id=preview.action_id, ledger_source=str(ledger_path))
    return build_agent_packet_report(events, action_id=preview.action_id, ledger_source=str(ledger_path))


def _command_center(
    workspace: Path,
    state_data: JsonMap,
    timeline: MissionTimelineReport,
    preview: ApprovalPreviewReport | None,
    active_request: JsonMap | None,
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
            "command": (
                f"delegation approval-preview {preview.agent_id} --workspace {workspace} "
                f"--action {preview.action} --target {preview.target}"
                f"{_preview_metadata_args(preview)}"
            ),
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
        if preview.ledger:
            yield {
                "id": "export_agent_packet",
                "label": "Export agent packet",
                "command": (
                    f"delegation agent-packet --ledger {preview.ledger} --action-id {preview.action_id} "
                    "--output .delegation/agent-packet.json"
                ),
                "purpose": "Create the job card for a custom agent after a gate receipt exists.",
                "risk": "none",
            }
            yield {
                "id": "ingest_agent_result",
                "label": "Ingest agent result",
                "command": (
                    f"delegation agent-result-ingest --ledger {preview.ledger} --action-id {preview.action_id} "
                    "--result .delegation/agent-result.json"
                ),
                "purpose": "Validate the worker result against the packet and append proof.",
                "risk": preview.gate.effective_risk,
            }
            yield {
                "id": "ingest_evidence",
                "label": "Attach evidence",
                "command": (
                    f"delegation evidence-ingest --ledger {preview.ledger} --action-id {preview.action_id} "
                    "--tool TOOL --recording-id REC --bundle-id BUNDLE --artifact PATH"
                ),
                "purpose": "Attach proof from any compatible recorder, test reporter, monitor, or workflow tool.",
                "risk": preview.gate.effective_risk,
            }
    ledger = state_data.get("ledger") if isinstance(state_data.get("ledger"), dict) else {}
    ledger_path = ledger.get("path")
    if isinstance(ledger_path, str) and ledger_path:
        approval_inbox = ledger.get("approval_inbox") if isinstance(ledger.get("approval_inbox"), dict) else {}
        latest_request = active_request or _latest_request_card(approval_inbox)
        if latest_request:
            action_id = latest_request.get("action_id")
            status = latest_request.get("status")
            if isinstance(action_id, str) and action_id:
                yield {
                    "id": "request_status",
                    "label": "Check request status",
                    "command": f"delegation request-status --ledger {ledger_path} --action-id {action_id}",
                    "purpose": "Show whether the latest request is pending, approved, blocked, recorded, or ready to run.",
                    "risk": "none",
                }
                if status in {"approved", "needs_evidence", "ready_for_recording"}:
                    yield {
                        "id": "request_run",
                        "label": "Run approved request",
                        "command": f"delegation request-run --ledger {ledger_path} --action-id {action_id} --confirm LOCAL_AGENT_EXECUTION",
                        "purpose": "Run only after the request card is cleared by Agent Gate and approvals.",
                        "risk": latest_request.get("risk", "medium"),
                    }
        yield {
            "id": "timeline",
            "label": "Review timeline",
            "command": f"delegation timeline --ledger {ledger_path}",
            "purpose": timeline.next_action,
            "risk": "none",
        }


def _latest_request_card(inbox: JsonMap) -> JsonMap | None:
    items = inbox.get("items") if isinstance(inbox.get("items"), list) else []
    for item in reversed(items):
        if isinstance(item, dict):
            return item
    return None


def _control_loop(
    state_data: JsonMap,
    timeline: MissionTimelineReport,
    preview: ApprovalPreviewReport | None,
    agent_packet: AgentPacketReport | None,
    command_center: T.Sequence[JsonMap],
) -> T.Iterator[JsonMap]:
    workspace = state_data.get("workspace") if isinstance(state_data.get("workspace"), dict) else {}
    ledger = state_data.get("ledger") if isinstance(state_data.get("ledger"), dict) else {}
    agents = state_data.get("agents") if isinstance(state_data.get("agents"), dict) else {}
    approval_inbox = ledger.get("approval_inbox") if isinstance(ledger.get("approval_inbox"), dict) else {}
    evidence = ledger.get("evidence") if isinstance(ledger.get("evidence"), dict) else {}
    passport_count = agents.get("passport_count", 0) if isinstance(agents.get("passport_count"), int) else 0
    event_count = ledger.get("event_count", 0) if isinstance(ledger.get("event_count"), int) else 0
    recorded_count = evidence.get("recorded_count", 0) if isinstance(evidence.get("recorded_count"), int) else 0
    pending_count = approval_inbox.get("pending_count", 0) if isinstance(approval_inbox.get("pending_count"), int) else 0

    yield {
        "id": "workspace",
        "title": "Workspace",
        "status": _string(workspace.get("status"), default="missing") if workspace else "missing",
        "summary": "A local workspace is ready." if workspace else "Create or select a workspace.",
        "next_action": _first_command(command_center, "refresh_dashboard") or "delegation workspace-init --path . --plan",
    }
    yield {
        "id": "mission",
        "title": "Mission",
        "status": _string(ledger.get("status"), default="missing") if event_count else "missing",
        "summary": f"{event_count} ledger event(s) loaded." if event_count else "Create the first dry-run mission plan.",
        "next_action": timeline.next_action,
    }
    yield {
        "id": "agent",
        "title": "Agent",
        "status": _string(agents.get("status"), default="missing") if passport_count else "missing",
        "summary": f"{passport_count} Agent Passport(s) registered." if passport_count else "Register a Bring Your Own Agent passport.",
        "next_action": _first_command(command_center, "preview_request") or "delegation agent-add AGENT_ID --workspace . --command COMMAND --capability read.workspace",
    }
    yield {
        "id": "gate",
        "title": "Gate",
        "status": preview.gate.decision if preview else "missing",
        "summary": (
            f"{preview.agent_id} wants `{preview.action}` on `{preview.target}`."
            if preview
            else "Preview the request before live action."
        ),
        "next_action": _first_command(command_center, "preview_request") or "delegation approval-preview AGENT_ID --workspace .",
    }
    yield {
        "id": "approval",
        "title": "Approval",
        "status": _approval_loop_status(preview, pending_count),
        "summary": _approval_loop_summary(preview, pending_count),
        "next_action": _first_command(command_center, "approve_request")
        or _first_command(command_center, "block_request")
        or _first_command(command_center, "preview_request")
        or "No human decision needed yet.",
    }
    yield {
        "id": "execution",
        "title": "Execution",
        "status": _execution_loop_status(preview, agent_packet),
        "summary": _execution_loop_summary(preview, agent_packet),
        "next_action": _first_command(command_center, "execute_agent")
        or _first_command(command_center, "export_agent_packet")
        or "Wait until the gate allows execution.",
    }
    yield {
        "id": "evidence",
        "title": "Evidence",
        "status": "recorded" if recorded_count or timeline.stage_counts.get("record", 0) else "missing",
        "summary": (
            f"{recorded_count or timeline.stage_counts.get('record', 0)} proof event(s) recorded."
            if recorded_count or timeline.stage_counts.get("record", 0)
            else "Attach proof from any compatible evidence tool."
        ),
        "next_action": _first_command(command_center, "ingest_evidence")
        or _first_command(command_center, "ingest_agent_result")
        or "delegation evidence-ingest --ledger .delegation/run.jsonl --tool TOOL --action-id ACTION_ID --recording-id REC --bundle-id BUNDLE --artifact PATH",
    }
    yield {
        "id": "timeline_eval",
        "title": "Timeline + Eval",
        "status": timeline.status,
        "summary": f"{timeline.event_count} timeline event(s), {timeline.attention_count} needing attention.",
        "next_action": _first_command(command_center, "timeline") or "Review the timeline, then run evals before promotion.",
    }


def _approval_loop_status(preview: ApprovalPreviewReport | None, pending_count: int) -> str:
    if preview is None:
        return "missing"
    if preview.gate.decision == "approval_required":
        return "pending" if pending_count else "approval_required"
    if preview.gate.decision == "allow":
        return "not_required"
    return preview.gate.decision


def _approval_loop_summary(preview: ApprovalPreviewReport | None, pending_count: int) -> str:
    if preview is None:
        return "No approval card yet."
    if preview.gate.decision == "approval_required":
        return f"{pending_count} approval card(s) waiting for a human decision."
    if preview.gate.decision == "allow":
        return "Gate allows this request without extra human approval."
    if preview.gate.decision == "block":
        return "Gate blocks this request."
    return "Review the warning before execution."


def _execution_loop_status(preview: ApprovalPreviewReport | None, packet: AgentPacketReport | None) -> str:
    if preview is None:
        return "missing"
    if preview.gate.decision == "block":
        return "blocked"
    if packet and packet.status == "recorded":
        return "recorded"
    if packet and packet.packet and packet.packet.get("can_execute"):
        return "ready"
    return "waiting"


def _execution_loop_summary(preview: ApprovalPreviewReport | None, packet: AgentPacketReport | None) -> str:
    if preview is None:
        return "No gated request exists yet."
    if packet and packet.status == "recorded":
        return "Execution already has evidence recorded."
    if packet and packet.packet and packet.packet.get("can_execute"):
        return "Agent Packet is cleared for controlled execution."
    if packet:
        return f"Agent Packet is `{packet.status}`."
    return "Create an Agent Gate receipt before handing work to an agent."


def _product_areas(
    state_data: JsonMap,
    timeline: MissionTimelineReport,
    preview: ApprovalPreviewReport | None,
    agent_packet: AgentPacketReport | None,
    command_center: T.Sequence[JsonMap],
) -> T.Iterator[JsonMap]:
    ledger = state_data.get("ledger") if isinstance(state_data.get("ledger"), dict) else {}
    dashboard = ledger.get("dashboard") if isinstance(ledger.get("dashboard"), dict) else {}
    mission = dashboard.get("mission") if isinstance(dashboard.get("mission"), dict) else {}
    agents = state_data.get("agents") if isinstance(state_data.get("agents"), dict) else {}
    approval_inbox = ledger.get("approval_inbox") if isinstance(ledger.get("approval_inbox"), dict) else {}
    evidence = ledger.get("evidence") if isinstance(ledger.get("evidence"), dict) else {}
    doctor = state_data.get("doctor") if isinstance(state_data.get("doctor"), dict) else {}
    release = state_data.get("release") if isinstance(state_data.get("release"), dict) else {}
    workspace = state_data.get("workspace") if isinstance(state_data.get("workspace"), dict) else {}

    yield {
        "id": "missions",
        "title": "Missions",
        "status": _string(mission.get("status") or ledger.get("status"), default="not_started"),
        "summary": _string(mission.get("objective"), default="Create or select a workspace mission."),
        "metrics": {
            "ledger_events": ledger.get("event_count", 0),
            "timeline_events": timeline.event_count,
            "attention": timeline.attention_count,
        },
        "next_action": timeline.next_action,
        "functional": True,
    }
    yield {
        "id": "agents",
        "title": "Agents",
        "status": _string(agents.get("status"), default="not_started"),
        "summary": f"{agents.get('passport_count', 0)} registered Agent Passport(s).",
        "metrics": {
            "passports": agents.get("passport_count", 0),
            "workspace_bound": bool(workspace),
        },
        "next_action": _first_command(command_center, "preview_request") or "Register or preview an agent passport.",
        "functional": True,
    }
    yield {
        "id": "approval_inbox",
        "title": "Approval Inbox",
        "status": _approval_area_status(preview, approval_inbox),
        "summary": _approval_area_summary(preview, approval_inbox),
        "metrics": {
            "pending": approval_inbox.get("pending_count", 0),
            "approved": approval_inbox.get("approved_count", 0),
            "blocked": approval_inbox.get("blocked_count", 0),
        },
        "next_action": _first_command(command_center, "approve_request")
        or _first_command(command_center, "preview_request")
        or approval_inbox.get("next_action")
        or "Create an Agent Gate receipt before approvals.",
        "functional": True,
    }
    yield {
        "id": "evidence",
        "title": "Evidence",
        "status": _evidence_area_status(timeline, agent_packet, evidence),
        "summary": _evidence_area_summary(timeline, agent_packet, evidence),
        "metrics": {
            "bundles": evidence.get("bundle_count", 0),
            "recorded": evidence.get("recorded_count", 0),
            "record_events": timeline.stage_counts.get("record", 0),
            "packet": agent_packet.status if agent_packet else "missing",
        },
        "next_action": _first_command(command_center, "ingest_agent_result")
        or _first_command(command_center, "ingest_evidence")
        or _first_command(command_center, "export_agent_packet")
        or "Attach recorder evidence after execution.",
        "functional": True,
    }
    yield {
        "id": "settings",
        "title": "Settings",
        "status": _settings_status(doctor, release),
        "summary": "Local-first mode. GitHub, models, and live actions stay optional adapters.",
        "metrics": {
            "doctor": doctor.get("status", "unknown"),
            "release": release.get("status", "unknown"),
            "read_only": state_data.get("read_only", True),
        },
        "next_action": _first_command(command_center, "refresh_dashboard") or "Refresh dashboard.",
        "functional": True,
    }


def _approval_area_status(preview: ApprovalPreviewReport | None, inbox: JsonMap) -> str:
    if preview:
        return preview.gate.decision
    return _string(inbox.get("status"), default="empty")


def _approval_area_summary(preview: ApprovalPreviewReport | None, inbox: JsonMap) -> str:
    if preview:
        return f"{preview.agent_id} wants `{preview.action}` on `{preview.target}`. Risk: {preview.gate.effective_risk}."
    pending = inbox.get("pending_count", 0)
    if pending:
        return f"{pending} approval card(s) need a human decision."
    return "No active approval card yet."


def _evidence_area_status(
    timeline: MissionTimelineReport,
    packet: AgentPacketReport | None,
    evidence: JsonMap,
) -> str:
    if evidence.get("recorded_count", 0):
        return "recorded"
    if timeline.stage_counts.get("record", 0):
        return "recorded"
    if packet and packet.status in {"ready_for_agent", "needs_approval", "needs_review"}:
        return "waiting"
    return _string(evidence.get("status"), default="not_started")


def _evidence_area_summary(
    timeline: MissionTimelineReport,
    packet: AgentPacketReport | None,
    evidence: JsonMap,
) -> str:
    record_events = timeline.stage_counts.get("record", 0)
    recorded_count = evidence.get("recorded_count", 0)
    if recorded_count:
        return f"{recorded_count} recorded proof item(s) from evidence tools."
    if record_events:
        return f"{record_events} recorded proof event(s) in the mission timeline."
    if packet:
        return f"Agent Packet is `{packet.status}`; result ingest is the evidence return lane."
    bundle_count = evidence.get("bundle_count", 0)
    if bundle_count:
        return f"{bundle_count} planned evidence bundle(s)."
    return "No recorder evidence has been recorded yet."


def _settings_status(doctor: JsonMap, release: JsonMap) -> str:
    if doctor.get("status") == "blocked" or release.get("status") == "failed":
        return "needs_attention"
    if doctor.get("status") == "ready":
        return "ready"
    return _string(doctor.get("status"), default="unknown")


def _first_command(commands: T.Sequence[JsonMap], command_id: str) -> str | None:
    for command in commands:
        if command.get("id") == command_id and isinstance(command.get("command"), str):
            return command["command"]
    return None


def _dashboard_warnings(
    state_data: JsonMap,
    timeline: MissionTimelineReport,
    preview: ApprovalPreviewReport | None,
    agent_packet: AgentPacketReport | None,
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
    if agent_packet and agent_packet.warnings:
        yield from agent_packet.warnings


def _preview_metadata_args(preview: ApprovalPreviewReport) -> str:
    parts: list[str] = []
    if preview.reviewer_note:
        parts.append("--review-note " + _shell_arg(preview.reviewer_note))
    if preview.expires_at:
        parts.append("--expires-at " + _shell_arg(preview.expires_at))
    return " " + " ".join(parts) if parts else ""


def _shell_arg(value: str) -> str:
    if not any(char.isspace() for char in value) and '"' not in value:
        return value
    return '"' + value.replace('"', '\\"') + '"'


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


def _string(value: T.Any, *, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default
