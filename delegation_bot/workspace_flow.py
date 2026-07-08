#!/usr/bin/env python3
"""Guided local workspace flow for the DelegationHQ cockpit."""

from __future__ import annotations

import typing as T
from dataclasses import dataclass
from pathlib import Path

from delegation_bot.app_state import AppState, build_app_state
from delegation_bot.mission_timeline import MissionTimelineReport, build_timeline_report_from_paths


JsonMap = dict[str, T.Any]
WORKSPACE_FLOW_SCHEMA_VERSION = "delegation.workspace-flow.v1"


@dataclass(frozen=True)
class WorkspaceFlowStep:
    id: str
    title: str
    status: str
    summary: str
    command: str
    risk: str = "none"

    @property
    def done(self) -> bool:
        return self.status in {"ready", "submitted", "cleared", "recorded", "review_ready", "approved"}

    @property
    def needs_attention(self) -> bool:
        return self.status in {"missing", "not_started", "pending_approval", "blocked", "waiting"}

    def to_dict(self) -> JsonMap:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "summary": self.summary,
            "command": self.command,
            "risk": self.risk,
            "done": self.done,
            "needs_attention": self.needs_attention,
        }


@dataclass(frozen=True)
class WorkspaceFlowReport:
    schema_version: str
    status: str
    workspace: str
    current_step: str
    next_command: str
    steps: tuple[WorkspaceFlowStep, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "workspace": self.workspace,
            "current_step": self.current_step,
            "next_command": self.next_command,
            "steps": [step.to_dict() for step in self.steps],
            "warnings": list(self.warnings),
        }


def build_workspace_flow_report(
    *,
    workspace_root: Path,
    state: AppState | None = None,
    timeline: MissionTimelineReport | None = None,
) -> WorkspaceFlowReport:
    workspace = workspace_root.resolve()
    state = state or build_app_state(workspace_root=workspace)
    timeline = timeline or build_timeline_report_from_paths(workspace_root=workspace, limit=0)
    state_data = state.to_dict()
    steps = tuple(_flow_steps(workspace=workspace, state_data=state_data, timeline=timeline.to_dict()))
    current = _current_step(steps)
    return WorkspaceFlowReport(
        schema_version=WORKSPACE_FLOW_SCHEMA_VERSION,
        status=_flow_status(steps),
        workspace=str(workspace),
        current_step=current.id if current else "complete",
        next_command=current.command if current else f"delegation timeline --workspace {workspace}",
        steps=steps,
        warnings=tuple(_flow_warnings(state_data)),
    )


def render_workspace_flow_report(report: WorkspaceFlowReport) -> str:
    lines = [
        "DelegationHQ Workspace Flow",
        "",
        f"Status: {report.status}",
        f"Workspace: {report.workspace}",
        f"Current step: {report.current_step}",
        "",
        "Flow:",
    ]
    for step in report.steps:
        marker = "done" if step.done else "next" if step.id == report.current_step else "wait"
        lines.append(f"- [{marker}] {step.title}: {step.status}")
        lines.append(f"  {step.summary}")
        if step.command:
            lines.append(f"  command: {step.command}")
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend(
        [
            "",
            "Plain language:",
            "- This is the simple path through the local trust cockpit.",
            "- Each step points to one safe next command.",
            "",
            "Next:",
            f"- {report.next_command}",
        ]
    )
    return "\n".join(lines)


def _flow_steps(*, workspace: Path, state_data: JsonMap, timeline: JsonMap) -> T.Iterator[WorkspaceFlowStep]:
    workspace_data = state_data.get("workspace") if isinstance(state_data.get("workspace"), dict) else {}
    ledger = state_data.get("ledger") if isinstance(state_data.get("ledger"), dict) else {}
    agents = state_data.get("agents") if isinstance(state_data.get("agents"), dict) else {}
    inbox = ledger.get("approval_inbox") if isinstance(ledger.get("approval_inbox"), dict) else {}
    evidence = ledger.get("evidence") if isinstance(ledger.get("evidence"), dict) else {}
    latest = _latest_request(inbox)
    agent_id = _first_agent_id(agents) or "AGENT_ID"
    action_id = _string(latest.get("action_id") if latest else "") or "ACTION_ID"
    request_status = _string(latest.get("status") if latest else "") or "not_started"
    record_count = _int(evidence.get("recorded_count")) + _timeline_stage_count(timeline, "record")
    passport_count = _int(agents.get("passport_count"))

    yield WorkspaceFlowStep(
        id="workspace",
        title="Open Workspace",
        status=_string(workspace_data.get("status"), default="missing") if workspace_data else "missing",
        summary="The folder is initialized as a DelegationHQ workspace." if workspace_data else "Create a local workspace first.",
        command=f"delegation workspace-init --path {workspace} --plan",
    )
    yield WorkspaceFlowStep(
        id="agent",
        title="Add Agent",
        status="ready" if passport_count else "missing",
        summary=f"{passport_count} Agent Passport(s) registered." if passport_count else "Register a custom agent passport.",
        command=f'delegation agent-add {agent_id} --workspace {workspace} --command "COMMAND" --capability read.workspace --allowed-data workspace --evidence command_output',
    )
    yield WorkspaceFlowStep(
        id="request",
        title="Submit Request",
        status="submitted" if latest else "not_started",
        summary=_request_summary(latest, agent_id=agent_id) if latest else "Ask DelegationHQ to gate an agent action before execution.",
        command=f"delegation action-request {agent_id} --workspace {workspace} --action read.workspace --target workspace --summary \"Agent requests workspace access.\"",
        risk=_string(latest.get("risk") if latest else "", default="low"),
    )
    yield WorkspaceFlowStep(
        id="approval",
        title="Approve Or Block",
        status=_approval_status(request_status),
        summary=_approval_summary(request_status),
        command=f"delegation approval-decision --ledger {_ledger_path(ledger, workspace)} --action-id {action_id} --decision approve --approver NAME",
        risk=_string(latest.get("risk") if latest else "", default="medium"),
    )
    yield WorkspaceFlowStep(
        id="execution",
        title="Run Under Control",
        status=_execution_status(request_status, record_count),
        summary=_execution_summary(request_status, record_count),
        command=f"delegation request-run --workspace {workspace} --action-id {action_id} --confirm LOCAL_AGENT_EXECUTION",
        risk=_string(latest.get("risk") if latest else "", default="medium"),
    )
    yield WorkspaceFlowStep(
        id="evidence",
        title="Record Evidence",
        status="recorded" if record_count else "waiting",
        summary=f"{record_count} proof event(s) recorded." if record_count else "Run the request or attach external evidence.",
        command=f"delegation evidence-ingest --ledger {_ledger_path(ledger, workspace)} --action-id {action_id} --tool TOOL --recording-id REC --bundle-id BUNDLE --artifact PATH",
    )
    yield WorkspaceFlowStep(
        id="review",
        title="Review Result",
        status="review_ready" if record_count else "waiting",
        summary="Review the timeline and evals before increasing trust." if record_count else "Wait for recorded evidence first.",
        command=f"delegation timeline --workspace {workspace}",
    )


def _latest_request(inbox: JsonMap) -> JsonMap | None:
    items = inbox.get("items") if isinstance(inbox.get("items"), list) else []
    for item in reversed(items):
        if isinstance(item, dict):
            return item
    return None


def _current_step(steps: T.Sequence[WorkspaceFlowStep]) -> WorkspaceFlowStep | None:
    for step in steps:
        if not step.done:
            return step
    return None


def _flow_status(steps: T.Sequence[WorkspaceFlowStep]) -> str:
    statuses = {step.status for step in steps}
    if statuses & {"blocked"}:
        return "blocked"
    if all(step.done for step in steps):
        return "complete"
    if statuses & {"pending_approval", "waiting"}:
        return "needs_attention"
    return "ready"


def _flow_warnings(state_data: JsonMap) -> T.Iterator[str]:
    workspace = state_data.get("workspace") if isinstance(state_data.get("workspace"), dict) else {}
    if not workspace:
        yield "No workspace data is loaded."
    agents = state_data.get("agents") if isinstance(state_data.get("agents"), dict) else {}
    if _int(agents.get("passport_count")) == 0:
        yield "No Agent Passports are registered yet."


def _request_summary(item: JsonMap | None, *, agent_id: str) -> str:
    if not item:
        return f"{agent_id} has not submitted an action request yet."
    summary = _string(item.get("request_summary") or item.get("title"))
    if summary:
        return summary
    return f"{_string(item.get('agent_id'), default=agent_id)} wants `{_string(item.get('action'), default='an action')}`."


def _approval_status(request_status: str) -> str:
    if request_status == "pending_approval":
        return "pending_approval"
    if request_status in {"approved", "needs_evidence", "ready_for_recording", "recorded"}:
        return "cleared"
    if request_status in {"blocked_by_human", "blocked_by_gate"}:
        return "blocked"
    return "not_started"


def _approval_summary(request_status: str) -> str:
    if request_status == "pending_approval":
        return "Human approval is needed before execution."
    if request_status in {"approved", "needs_evidence", "ready_for_recording", "recorded"}:
        return "Approval/gate state is clear enough to continue."
    if request_status in {"blocked_by_human", "blocked_by_gate"}:
        return "The request is blocked."
    return "No request is waiting for a human decision yet."


def _execution_status(request_status: str, record_count: int) -> str:
    if record_count:
        return "recorded"
    if request_status in {"approved", "needs_evidence", "ready_for_recording"}:
        return "ready"
    if request_status in {"blocked_by_human", "blocked_by_gate"}:
        return "blocked"
    if request_status == "pending_approval":
        return "waiting"
    return "not_started"


def _execution_summary(request_status: str, record_count: int) -> str:
    if record_count:
        return "Controlled execution evidence exists."
    if request_status in {"approved", "needs_evidence", "ready_for_recording"}:
        return "The request can run with the exact confirmation token."
    if request_status == "pending_approval":
        return "Wait for human approval before execution."
    if request_status in {"blocked_by_human", "blocked_by_gate"}:
        return "Execution is blocked."
    return "Submit and clear a request before execution."


def _ledger_path(ledger: JsonMap, workspace: Path) -> str:
    value = ledger.get("path") if isinstance(ledger.get("path"), str) else ""
    return value or str(workspace / ".delegation" / "agent-run.jsonl")


def _first_agent_id(agents: JsonMap) -> str | None:
    passports = agents.get("passports") if isinstance(agents.get("passports"), list) else []
    for passport in passports:
        if isinstance(passport, dict):
            value = _string(passport.get("id"))
            if value:
                return value
    return None


def _timeline_stage_count(timeline: JsonMap, stage: str) -> int:
    counts = timeline.get("stage_counts") if isinstance(timeline.get("stage_counts"), dict) else {}
    return _int(counts.get(stage))


def _string(value: T.Any, *, default: str = "") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _int(value: T.Any) -> int:
    return value if isinstance(value, int) else 0
