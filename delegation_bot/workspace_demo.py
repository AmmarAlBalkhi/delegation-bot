#!/usr/bin/env python3
"""One-command local workspace demo for DelegationHQ."""

from __future__ import annotations

import json
import sys
import typing as T
from dataclasses import dataclass
from pathlib import Path

from delegation_bot.action_request import (
    RequestRunReport,
    build_action_request_events,
    build_action_request_report,
    run_request_under_control,
)
from delegation_bot.agent_registry_writer import AgentAddReport, add_agent_to_registry
from delegation_bot.agent_run import LOCAL_AGENT_EXECUTION_CONFIRMATION
from delegation_bot.approval_inbox import build_approval_decision_events
from delegation_bot.evals import append_jsonl, load_jsonl
from delegation_bot.harness_manifest import load_manifest
from delegation_bot.local_app import LocalAppReport, export_local_app
from delegation_bot.local_workspace import (
    DEFAULT_WORKSPACE_AGENT_RUN_LEDGER,
    DEFAULT_WORKSPACE_HARNESS,
    DEFAULT_WORKSPACE_REGISTRY,
    WorkspaceInitReport,
    initialize_local_workspace,
)
from delegation_bot.workspace_flow import WorkspaceFlowReport, build_workspace_flow_report


JsonMap = dict[str, T.Any]
WORKSPACE_DEMO_SCHEMA_VERSION = "delegation.workspace-demo.v1"
DEMO_AGENT_ID = "demo_cli_agent"
DEMO_ACTION = "write.workspace"
DEMO_TARGET = "workspace"
DEMO_SUMMARY = "Demo agent wants to write a controlled local workspace note."


@dataclass(frozen=True)
class WorkspaceDemoReport:
    schema_version: str
    status: str
    workspace: str
    ledger: str
    action_id: str
    initialized: WorkspaceInitReport
    agent: AgentAddReport
    request: JsonMap
    approved: bool
    executed: bool
    run: RequestRunReport | None
    flow: WorkspaceFlowReport
    app_export: LocalAppReport | None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "workspace": self.workspace,
            "ledger": self.ledger,
            "action_id": self.action_id,
            "initialized": self.initialized.to_dict(),
            "agent": self.agent.to_dict(),
            "request": self.request,
            "approved": self.approved,
            "executed": self.executed,
            "run": self.run.to_dict() if self.run else None,
            "flow": self.flow.to_dict(),
            "app_export": self.app_export.to_dict() if self.app_export else None,
            "warnings": list(self.warnings),
            "next_actions": list(self.next_actions),
        }

    @property
    def next_actions(self) -> tuple[str, ...]:
        actions = [self.flow.next_command]
        if self.app_export and self.app_export.index_html:
            actions.append(f"Open {self.app_export.index_html}")
        actions.append(f"delegation app-dashboard --workspace {self.workspace} --preview-agent {DEMO_AGENT_ID}")
        return tuple(_dedupe(actions))


def build_workspace_demo_report(
    *,
    workspace_root: Path,
    force: bool = False,
    approve: bool = False,
    execute: bool = False,
    confirm: str | None = None,
    export_app: bool = False,
    command: str | None = None,
) -> WorkspaceDemoReport:
    workspace = workspace_root.resolve()
    initialized = initialize_local_workspace(
        root=workspace,
        name="DelegationHQ Demo Workspace",
        owner="local-operator",
        objective="See a local agent ask, get gated, receive approval, run, and record evidence.",
        plan=True,
        force=force,
    )
    registry_path = workspace / DEFAULT_WORKSPACE_REGISTRY
    ledger_path = workspace / DEFAULT_WORKSPACE_AGENT_RUN_LEDGER
    harnessfile = workspace / DEFAULT_WORKSPACE_HARNESS
    agent = add_agent_to_registry(
        registry_path=registry_path,
        agent_id=DEMO_AGENT_ID,
        name="Demo CLI Agent",
        command=command or _default_demo_command(),
        capabilities=(DEMO_ACTION,),
        allowed_data=(DEMO_TARGET,),
        approvals=(DEMO_ACTION,),
        evidence=("command_output",),
        force=True,
    )
    manifest = load_manifest(harnessfile)
    existing_events = load_jsonl(ledger_path) if ledger_path.exists() else []
    request = build_action_request_report(
        agent_id=DEMO_AGENT_ID,
        action=DEMO_ACTION,
        target=DEMO_TARGET,
        ledger_source=str(ledger_path),
        manifest=manifest,
        manifest_source=str(harnessfile),
        registry_paths=(registry_path,),
        requested_by="workspace-demo",
        summary=DEMO_SUMMARY,
        wrote_ledger=True,
    )
    request_events = build_action_request_events(
        request,
        run_id=str(existing_events[0].get("run_id")) if existing_events else "workspace-demo",
        start_sequence=len(existing_events) + 1,
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    append_jsonl(request_events, ledger_path)
    approved = False
    if approve:
        ledger_events = load_jsonl(ledger_path)
        approval_events = build_approval_decision_events(
            ledger_events,
            action_id=request.action_id,
            decision="approve",
            approver="workspace-demo",
            reason="Demo flow approval.",
        )
        append_jsonl(approval_events, ledger_path)
        approved = True
    run_report = None
    if execute:
        if confirm != LOCAL_AGENT_EXECUTION_CONFIRMATION:
            raise ValueError(f"--execute requires --confirm {LOCAL_AGENT_EXECUTION_CONFIRMATION}")
        ledger_events = load_jsonl(ledger_path)
        run_report = run_request_under_control(
            ledger_events,
            ledger_path=ledger_path,
            action_id=request.action_id,
            registry_paths=(registry_path,),
            manifest=manifest,
            manifest_source=str(harnessfile),
            confirm=confirm,
            cwd=workspace,
            output_dir=workspace / ".delegation" / "agent-runs",
        )
    flow = build_workspace_flow_report(workspace_root=workspace)
    app_report = (
        export_local_app(workspace_root=workspace, preview_agent=DEMO_AGENT_ID)
        if export_app
        else None
    )
    return WorkspaceDemoReport(
        schema_version=WORKSPACE_DEMO_SCHEMA_VERSION,
        status=_status(approved=approved, run=run_report, flow=flow),
        workspace=str(workspace),
        ledger=str(ledger_path),
        action_id=request.action_id,
        initialized=initialized,
        agent=agent,
        request=request.to_dict(),
        approved=approved,
        executed=bool(run_report and not run_report.blocked),
        run=run_report,
        flow=flow,
        app_export=app_report,
        warnings=(),
    )


def render_workspace_demo_report(report: WorkspaceDemoReport) -> str:
    lines = [
        "DelegationHQ Workspace Demo",
        "",
        f"Status: {report.status}",
        f"Workspace: {report.workspace}",
        f"Ledger: {report.ledger}",
        f"Agent: {report.agent.agent_id}",
        f"Action: {report.action_id}",
        f"Approved: {str(report.approved).lower()}",
        f"Executed: {str(report.executed).lower()}",
        "",
        "What happened:",
        "- local workspace initialized",
        "- demo Agent Passport registered",
        "- action request submitted and gated",
    ]
    if report.approved:
        lines.append("- approval receipt recorded")
    if report.executed:
        lines.append("- request ran under control and evidence was recorded")
    if report.app_export and report.app_export.index_html:
        lines.append(f"- cockpit exported: {report.app_export.index_html}")
    lines.extend(
        [
            "",
            "Flow:",
            f"- status: {report.flow.status}",
            f"- current step: {report.flow.current_step}",
            "",
            "Plain language:",
            "- This creates a real local DelegationHQ workspace you can inspect.",
            "- Nothing runs unless you pass --execute with the exact confirmation token.",
            "",
            "Next:",
        ]
    )
    lines.extend(f"- {action}" for action in report.next_actions)
    return "\n".join(lines)


def _default_demo_command() -> str:
    return f"{sys.executable} -c \"print('workspace demo agent ok')\""


def _status(*, approved: bool, run: RequestRunReport | None, flow: WorkspaceFlowReport) -> str:
    if run and run.blocked:
        return "blocked"
    if run and not run.blocked:
        return "recorded"
    if approved:
        return "approved"
    return flow.status


def _dedupe(values: T.Iterable[str]) -> T.Iterator[str]:
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            yield value
