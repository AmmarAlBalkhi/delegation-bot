#!/usr/bin/env python3
"""Local app shell export and server for DelegationHQ."""

from __future__ import annotations

import html
import hashlib
import json
import typing as T
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from delegation_bot.app_dashboard import build_app_dashboard_report
from delegation_bot.app_state import build_app_state
from delegation_bot.approval_inbox import build_approval_decision_events, build_approval_inbox_report
from delegation_bot.approval_preview import ApprovalPreviewReport, build_approval_preview_report
from delegation_bot.evals import append_jsonl, load_jsonl
from delegation_bot.agent_registry_writer import add_agent_to_registry
from delegation_bot.local_workspace import DEFAULT_WORKSPACE_AGENT_RUN_LEDGER, DEFAULT_WORKSPACE_REGISTRY
from delegation_bot.mission_timeline import build_timeline_report_from_paths


JsonMap = dict[str, T.Any]
DEFAULT_APP_DIR = ".delegation/cockpit"
DEFAULT_APP_HOST = "127.0.0.1"
DEFAULT_APP_PORT = 8765
LOCAL_APP_WRITE_CONFIRMATION = "LOCAL_APP_WRITE"
LOCAL_APP_ACTION_SCHEMA_VERSION = "delegation.local-app-action.v1"
LOCAL_APP_AGENT_SCHEMA_VERSION = "delegation.local-app-agent.v1"


@dataclass(frozen=True)
class LocalAppReport:
    status: str
    workspace: str
    output_dir: str | None
    index_html: str | None
    dashboard_json: str | None
    state_json: str | None
    timeline_json: str | None
    approval_preview_json: str | None
    url: str | None
    preview_agent: str | None
    actions_enabled: bool = False
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> JsonMap:
        return {
            "status": self.status,
            "workspace": self.workspace,
            "output_dir": self.output_dir,
            "index_html": self.index_html,
            "dashboard_json": self.dashboard_json,
            "state_json": self.state_json,
            "timeline_json": self.timeline_json,
            "approval_preview_json": self.approval_preview_json,
            "url": self.url,
            "preview_agent": self.preview_agent,
            "actions_enabled": self.actions_enabled,
            "warnings": list(self.warnings),
            "next_actions": list(self.next_actions),
        }

    @property
    def next_actions(self) -> tuple[str, ...]:
        actions: list[str] = []
        if self.index_html:
            actions.append(f"Open {self.index_html} in a browser.")
        if self.url:
            actions.append(f"Open {self.url} in a browser.")
        actions.append(f"delegation app-state --workspace {self.workspace} --json")
        if self.preview_agent:
            actions.append(f"delegation approval-preview {self.preview_agent} --workspace {self.workspace}")
        if not self.actions_enabled:
            actions.append(
                "Start with `delegation app-serve --workspace . --allow-actions` "
                "only when you want guarded local approval writes."
            )
        return tuple(actions)


@dataclass(frozen=True)
class LocalAppActionReport:
    schema_version: str
    status: str
    action: str
    workspace: str
    ledger: str
    action_id: str
    decision: str
    approver: str
    wrote_ledger: bool
    message: str
    warnings: tuple[str, ...] = ()

    @property
    def next_actions(self) -> tuple[str, ...]:
        if self.status == "recorded" and self.decision == "approve":
            return (
                f"delegation request-run --ledger {self.ledger} --action-id {self.action_id} --confirm LOCAL_AGENT_EXECUTION",
                f"delegation request-status --ledger {self.ledger} --action-id {self.action_id}",
            )
        if self.status == "recorded":
            return (f"delegation request-status --ledger {self.ledger} --action-id {self.action_id}",)
        return ("Refresh `/api/dashboard` and review the active request.",)

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "action": self.action,
            "workspace": self.workspace,
            "ledger": self.ledger,
            "action_id": self.action_id,
            "decision": self.decision,
            "approver": self.approver,
            "wrote_ledger": self.wrote_ledger,
            "message": self.message,
            "warnings": list(self.warnings),
            "next_actions": list(self.next_actions),
        }


@dataclass(frozen=True)
class LocalAppAgentReport:
    schema_version: str
    status: str
    action: str
    workspace: str
    registry: str
    agent_id: str
    runtime_type: str
    wrote_registry: bool
    message: str
    warnings: tuple[str, ...] = ()

    @property
    def next_actions(self) -> tuple[str, ...]:
        if self.status == "recorded":
            return (
                f"delegation agents --registry {self.registry}",
                f"delegation approval-preview {self.agent_id} --workspace {self.workspace}",
                "Refresh `/api/dashboard` to see the Agent Passport.",
            )
        return ("Refresh `/api/dashboard` and review the agent form.",)

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "action": self.action,
            "workspace": self.workspace,
            "registry": self.registry,
            "agent_id": self.agent_id,
            "runtime_type": self.runtime_type,
            "wrote_registry": self.wrote_registry,
            "message": self.message,
            "warnings": list(self.warnings),
            "next_actions": list(self.next_actions),
        }


def export_local_app(
    *,
    workspace_root: Path,
    output_dir: Path | None = None,
    preview_agent: str | None = None,
    preview_action: str = "read.workspace",
    preview_target: str = "workspace",
    preview_note: str | None = None,
    preview_expires_at: str | None = None,
) -> LocalAppReport:
    """Write a static local cockpit bundle for a workspace."""

    workspace = workspace_root.resolve()
    target_dir = (output_dir or workspace / DEFAULT_APP_DIR).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    dashboard = build_app_dashboard_report(
        workspace_root=workspace,
        preview_agent=preview_agent,
        preview_action=preview_action,
        preview_target=preview_target,
        preview_note=preview_note,
        preview_expires_at=preview_expires_at,
    )
    dashboard_data = dashboard.to_dict()
    state_data = dashboard_data["state"]
    preview_data = dashboard_data.get("approval_preview")
    agent_packet_data = dashboard_data.get("agent_packet")
    timeline_data = dashboard_data["timeline"]

    dashboard_path = target_dir / "dashboard.json"
    state_path = target_dir / "state.json"
    timeline_path = target_dir / "timeline.json"
    preview_path = target_dir / "approval-preview.json"
    agent_packet_path = target_dir / "agent-packet.json"
    index_path = target_dir / "index.html"
    dashboard_path.write_text(json.dumps(dashboard_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    state_path.write_text(json.dumps(state_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    timeline_path.write_text(json.dumps(timeline_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if preview_data:
        preview_path.write_text(json.dumps(preview_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if agent_packet_data:
        agent_packet_path.write_text(json.dumps(agent_packet_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    index_path.write_text(_render_app_html(dashboard_data), encoding="utf-8")

    return LocalAppReport(
        status="ready",
        workspace=str(workspace),
        output_dir=str(target_dir),
        index_html=str(index_path),
        dashboard_json=str(dashboard_path),
        state_json=str(state_path),
        timeline_json=str(timeline_path),
        approval_preview_json=str(preview_path) if preview_data else None,
        url=index_path.as_uri(),
        preview_agent=dashboard.approval_preview.agent_id if dashboard.approval_preview else None,
    )


def build_local_app_approval_decision(
    *,
    workspace_root: Path,
    actions_enabled: bool,
    action_id: str | None = None,
    decision: str = "",
    approver: str = "",
    reason: str = "",
    confirm: str | None = None,
) -> LocalAppActionReport:
    """Record a guarded local approval decision for the active request."""

    workspace = workspace_root.resolve()
    ledger = workspace / DEFAULT_WORKSPACE_AGENT_RUN_LEDGER
    clean_action_id = _clean(action_id)
    clean_decision = _clean(decision).lower()
    clean_approver = _clean(approver)
    clean_reason = _clean(reason)
    if not actions_enabled:
        return _local_app_action_refused(
            workspace=workspace,
            ledger=ledger,
            action_id=clean_action_id,
            decision=clean_decision,
            approver=clean_approver,
            status="disabled",
            message="Local app actions are disabled. Restart with --allow-actions to enable guarded approval writes.",
        )
    if confirm != LOCAL_APP_WRITE_CONFIRMATION:
        return _local_app_action_refused(
            workspace=workspace,
            ledger=ledger,
            action_id=clean_action_id,
            decision=clean_decision,
            approver=clean_approver,
            status="blocked",
            message=f"Approval writes require confirmation token {LOCAL_APP_WRITE_CONFIRMATION}.",
        )
    if clean_decision not in {"approve", "block"}:
        return _local_app_action_refused(
            workspace=workspace,
            ledger=ledger,
            action_id=clean_action_id,
            decision=clean_decision,
            approver=clean_approver,
            status="blocked",
            message="Decision must be `approve` or `block`.",
        )
    if not clean_approver:
        return _local_app_action_refused(
            workspace=workspace,
            ledger=ledger,
            action_id=clean_action_id,
            decision=clean_decision,
            approver=clean_approver,
            status="blocked",
            message="Approver is required.",
        )
    if not ledger.exists():
        return _local_app_action_refused(
            workspace=workspace,
            ledger=ledger,
            action_id=clean_action_id,
            decision=clean_decision,
            approver=clean_approver,
            status="missing",
            message="No workspace request ledger exists yet.",
        )

    events = load_jsonl(ledger)
    selected_action_id = clean_action_id or _active_request_action_id(events, ledger_source=str(ledger))
    if not selected_action_id:
        return _local_app_action_refused(
            workspace=workspace,
            ledger=ledger,
            action_id=clean_action_id,
            decision=clean_decision,
            approver=clean_approver,
            status="missing",
            message="No active request card is available for approval.",
        )

    try:
        decision_events = build_approval_decision_events(
            events,
            action_id=selected_action_id,
            decision=clean_decision,
            approver=clean_approver,
            reason=clean_reason,
        )
    except ValueError as exc:
        return _local_app_action_refused(
            workspace=workspace,
            ledger=ledger,
            action_id=selected_action_id,
            decision=clean_decision,
            approver=clean_approver,
            status="blocked",
            message=str(exc),
        )
    append_jsonl(decision_events, ledger)
    return LocalAppActionReport(
        schema_version=LOCAL_APP_ACTION_SCHEMA_VERSION,
        status="recorded",
        action="approval-decision",
        workspace=str(workspace),
        ledger=str(ledger),
        action_id=selected_action_id,
        decision=clean_decision,
        approver=clean_approver,
        wrote_ledger=True,
        message=f"Human decision `{clean_decision}` recorded for `{selected_action_id}`.",
    )


def _local_app_action_refused(
    *,
    workspace: Path,
    ledger: Path,
    action_id: str,
    decision: str,
    approver: str,
    status: str,
    message: str,
    warnings: tuple[str, ...] = (),
) -> LocalAppActionReport:
    return LocalAppActionReport(
        schema_version=LOCAL_APP_ACTION_SCHEMA_VERSION,
        status=status,
        action="approval-decision",
        workspace=str(workspace),
        ledger=str(ledger),
        action_id=action_id,
        decision=decision,
        approver=approver,
        wrote_ledger=False,
        message=message,
        warnings=warnings,
    )


def _active_request_action_id(events: list[JsonMap], *, ledger_source: str) -> str | None:
    inbox = build_approval_inbox_report(events, ledger_source=ledger_source)
    priority = {
        "pending_approval": 0,
        "warning": 1,
        "approved": 2,
        "needs_evidence": 3,
        "ready_for_recording": 4,
        "blocked_by_human": 5,
        "blocked_by_gate": 6,
        "recorded": 7,
    }
    candidates = [
        item
        for item in inbox.items
        if isinstance(item.action_id, str) and item.action_id.strip()
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            priority.get(item.status, 99),
            item.sequence if item.sequence is not None else 999999,
        )
    )
    return candidates[0].action_id.strip()


def _clean(value: T.Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def build_local_app_agent_add(
    *,
    workspace_root: Path,
    actions_enabled: bool,
    agent_id: str = "",
    name: str = "",
    runtime_type: str = "cli.command",
    command: str = "",
    api_url: str = "",
    webhook_url: str = "",
    mcp_endpoint: str = "",
    capabilities: T.Sequence[str] = (),
    allowed_tools: T.Sequence[str] = (),
    allowed_data: T.Sequence[str] = (),
    approvals: T.Sequence[str] = (),
    expected_outputs: T.Sequence[str] = (),
    evidence: T.Sequence[str] = (),
    promotion_evals: T.Sequence[str] = (),
    confirm: str | None = None,
    force: bool = False,
) -> LocalAppAgentReport:
    """Register an Agent Passport through the guarded local app backend."""

    workspace = workspace_root.resolve()
    registry = workspace / DEFAULT_WORKSPACE_REGISTRY
    clean_agent_id = _clean(agent_id)
    clean_runtime = _clean(runtime_type) or "cli.command"
    if not actions_enabled:
        return _local_app_agent_refused(
            workspace=workspace,
            registry=registry,
            agent_id=clean_agent_id,
            runtime_type=clean_runtime,
            status="disabled",
            message="Local app actions are disabled. Restart with --allow-actions to register agents.",
        )
    if confirm != LOCAL_APP_WRITE_CONFIRMATION:
        return _local_app_agent_refused(
            workspace=workspace,
            registry=registry,
            agent_id=clean_agent_id,
            runtime_type=clean_runtime,
            status="blocked",
            message=f"Agent registration requires confirmation token {LOCAL_APP_WRITE_CONFIRMATION}.",
        )
    if not clean_agent_id:
        return _local_app_agent_refused(
            workspace=workspace,
            registry=registry,
            agent_id=clean_agent_id,
            runtime_type=clean_runtime,
            status="blocked",
            message="Agent id is required.",
        )
    try:
        report = add_agent_to_registry(
            registry_path=registry,
            agent_id=clean_agent_id,
            name=_clean(name) or None,
            runtime_type=clean_runtime,
            command=_clean(command) or None,
            api_url=_clean(api_url) or None,
            webhook_url=_clean(webhook_url) or None,
            mcp_endpoint=_clean(mcp_endpoint) or None,
            capabilities=tuple(_clean_list_values(capabilities)),
            allowed_tools=tuple(_clean_list_values(allowed_tools)),
            allowed_data=tuple(_clean_list_values(allowed_data)),
            approvals=tuple(_clean_list_values(approvals)),
            expected_outputs=tuple(_clean_list_values(expected_outputs)),
            evidence=tuple(_clean_list_values(evidence)),
            promotion_evals=tuple(_clean_list_values(promotion_evals)),
            force=force,
        )
    except (OSError, ValueError) as exc:
        return _local_app_agent_refused(
            workspace=workspace,
            registry=registry,
            agent_id=clean_agent_id,
            runtime_type=clean_runtime,
            status="blocked",
            message=str(exc),
        )
    return LocalAppAgentReport(
        schema_version=LOCAL_APP_AGENT_SCHEMA_VERSION,
        status="recorded",
        action="agent-add",
        workspace=str(workspace),
        registry=report.registry,
        agent_id=report.agent_id,
        runtime_type=report.runtime_type,
        wrote_registry=True,
        message=f"Agent `{report.agent_id}` registered in the local workspace.",
        warnings=report.warnings,
    )


def _local_app_agent_refused(
    *,
    workspace: Path,
    registry: Path,
    agent_id: str,
    runtime_type: str,
    status: str,
    message: str,
    warnings: tuple[str, ...] = (),
) -> LocalAppAgentReport:
    return LocalAppAgentReport(
        schema_version=LOCAL_APP_AGENT_SCHEMA_VERSION,
        status=status,
        action="agent-add",
        workspace=str(workspace),
        registry=str(registry),
        agent_id=agent_id,
        runtime_type=runtime_type,
        wrote_registry=False,
        message=message,
        warnings=warnings,
    )


def _clean_list_values(values: T.Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _payload_list(value: T.Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item) for item in value if isinstance(item, (str, int, float)))
    if isinstance(value, str):
        normalized = value.replace("\r\n", "\n").replace("\r", "\n").replace(",", "\n")
        return tuple(part.strip() for part in normalized.split("\n") if part.strip())
    return ()


def serve_local_app(
    *,
    workspace_root: Path,
    host: str = DEFAULT_APP_HOST,
    port: int = DEFAULT_APP_PORT,
    preview_agent: str | None = None,
    preview_action: str = "read.workspace",
    preview_target: str = "workspace",
    preview_note: str | None = None,
    preview_expires_at: str | None = None,
    allow_actions: bool = False,
) -> None:
    """Serve the local cockpit until interrupted."""

    workspace = workspace_root.resolve()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API.
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                dashboard_data = build_app_dashboard_report(
                    workspace_root=workspace,
                    preview_agent=preview_agent,
                    preview_action=preview_action,
                    preview_target=preview_target,
                    preview_note=preview_note,
                    preview_expires_at=preview_expires_at,
                ).to_dict()
                state_data = dashboard_data["state"]
                preview = _preview_from_query(
                    parse_qs(parsed.query),
                    state_data=state_data,
                    workspace_root=workspace,
                    default_agent=preview_agent,
                    default_action=preview_action,
                    default_target=preview_target,
                    default_note=preview_note,
                    default_expires_at=preview_expires_at,
                )
                if preview is not None:
                    dashboard_data["approval_preview"] = preview.to_dict()
                self._send_text(_render_app_html(dashboard_data), "text/html")
                return
            if parsed.path == "/api/state":
                self._send_json(build_app_state(workspace_root=workspace).to_dict())
                return
            if parsed.path == "/api/dashboard":
                self._send_json(
                    build_app_dashboard_report(
                        workspace_root=workspace,
                        preview_agent=preview_agent,
                        preview_action=preview_action,
                        preview_target=preview_target,
                        preview_note=preview_note,
                        preview_expires_at=preview_expires_at,
                    ).to_dict()
                )
                return
            if parsed.path == "/api/timeline":
                self._send_json(build_timeline_report_from_paths(workspace_root=workspace, limit=0).to_dict())
                return
            if parsed.path == "/api/approval-preview":
                state_data = build_app_state(workspace_root=workspace).to_dict()
                preview = _preview_from_query(
                    parse_qs(parsed.query),
                    state_data=state_data,
                    workspace_root=workspace,
                    default_agent=preview_agent,
                    default_action=preview_action,
                    default_target=preview_target,
                    default_note=preview_note,
                    default_expires_at=preview_expires_at,
                )
                if preview is None:
                    self._send_json({"status": "empty", "message": "No agent passport is available."}, status=404)
                    return
                self._send_json(preview.to_dict())
                return
            if parsed.path == "/api/health":
                self._send_json({"status": "ready", "workspace": str(workspace), "actions_enabled": allow_actions})
                return
            self._send_json({"status": "missing", "path": parsed.path}, status=404)

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API.
            parsed = urlparse(self.path)
            if parsed.path not in {"/api/approval-decision", "/api/agent-add"}:
                self._send_json({"status": "missing", "path": parsed.path}, status=404)
                return
            payload = self._read_json()
            if parsed.path == "/api/approval-decision":
                report = build_local_app_approval_decision(
                    workspace_root=workspace,
                    actions_enabled=allow_actions,
                    action_id=_clean(payload.get("action_id")),
                    decision=_clean(payload.get("decision")),
                    approver=_clean(payload.get("approver")),
                    reason=_clean(payload.get("reason")),
                    confirm=_clean(payload.get("confirm")),
                )
                status = 200 if report.status == "recorded" else 403 if report.status == "disabled" else 400
                self._send_json(report.to_dict(), status=status)
                return
            report = build_local_app_agent_add(
                workspace_root=workspace,
                actions_enabled=allow_actions,
                agent_id=_clean(payload.get("agent_id")),
                name=_clean(payload.get("name")),
                runtime_type=_clean(payload.get("runtime_type")) or "cli.command",
                command=_clean(payload.get("command")),
                api_url=_clean(payload.get("api_url")),
                webhook_url=_clean(payload.get("webhook_url")),
                mcp_endpoint=_clean(payload.get("mcp_endpoint")),
                capabilities=_payload_list(payload.get("capabilities")),
                allowed_tools=_payload_list(payload.get("allowed_tools")),
                allowed_data=_payload_list(payload.get("allowed_data")),
                approvals=_payload_list(payload.get("approvals")),
                expected_outputs=_payload_list(payload.get("expected_outputs")),
                evidence=_payload_list(payload.get("evidence")),
                promotion_evals=_payload_list(payload.get("promotion_evals")),
                force=bool(payload.get("force")),
                confirm=_clean(payload.get("confirm")),
            )
            status = 200 if report.status == "recorded" else 403 if report.status == "disabled" else 400
            self._send_json(report.to_dict(), status=status)

        def log_message(self, format: str, *args: T.Any) -> None:  # noqa: A002 - stdlib signature.
            return

        def _send_text(self, value: str, content_type: str, *, status: int = 200) -> None:
            body = value.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, value: JsonMap, *, status: int = 200) -> None:
            self._send_text(json.dumps(value, indent=2, sort_keys=True) + "\n", "application/json", status=status)

        def _read_json(self) -> JsonMap:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0:
                return {}
            if length > 65536:
                return {"error": "request too large"}
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return {}
            return payload if isinstance(payload, dict) else {}

    server = ThreadingHTTPServer((host, port), Handler)
    server.serve_forever()


def app_server_report(
    *,
    workspace_root: Path,
    host: str = DEFAULT_APP_HOST,
    port: int = DEFAULT_APP_PORT,
    actions_enabled: bool = False,
) -> LocalAppReport:
    workspace = workspace_root.resolve()
    return LocalAppReport(
        status="ready",
        workspace=str(workspace),
        output_dir=None,
        index_html=None,
        dashboard_json=None,
        state_json=None,
        timeline_json=None,
        approval_preview_json=None,
        url=f"http://{host}:{port}/",
        preview_agent=_first_agent_id(build_app_state(workspace_root=workspace).to_dict()),
        actions_enabled=actions_enabled,
    )


def render_local_app_report(report: LocalAppReport) -> str:
    lines = [
        "DelegationHQ Local App",
        "",
        f"Status: {report.status}",
        f"Workspace: {report.workspace}",
    ]
    if report.output_dir:
        lines.append(f"Output: {report.output_dir}")
    if report.index_html:
        lines.append(f"HTML: {report.index_html}")
    if report.dashboard_json:
        lines.append(f"Dashboard JSON: {report.dashboard_json}")
    if report.state_json:
        lines.append(f"State JSON: {report.state_json}")
    if report.timeline_json:
        lines.append(f"Timeline JSON: {report.timeline_json}")
    if report.approval_preview_json:
        lines.append(f"Approval Preview JSON: {report.approval_preview_json}")
    if report.url:
        lines.append(f"URL: {report.url}")
    if report.preview_agent:
        lines.append(f"Preview agent: {report.preview_agent}")
    lines.append(f"Actions enabled: {str(report.actions_enabled).lower()}")
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend(
        [
            "",
            "Plain language:",
            "- This is a local app shell over the DelegationHQ control plane.",
            "- It is read-only by default.",
            f"- Approval writes require `--allow-actions` and `{LOCAL_APP_WRITE_CONFIRMATION}`.",
            "- Agent execution still requires the separate `LOCAL_AGENT_EXECUTION` confirmation.",
        ]
    )
    lines.extend(["", "Next:"])
    lines.extend(f"- {action}" for action in report.next_actions)
    return "\n".join(lines)


def _preview_from_query(
    query: dict[str, list[str]],
    *,
    state_data: JsonMap,
    workspace_root: Path,
    default_agent: str | None,
    default_action: str,
    default_target: str,
    default_note: str | None = None,
    default_expires_at: str | None = None,
) -> ApprovalPreviewReport | None:
    agent = _query_value(query, "agent") or default_agent or _first_agent_id(state_data)
    if not agent:
        return None
    return build_approval_preview_report(
        agent_id=agent,
        action=_query_value(query, "action") or default_action,
        target=_query_value(query, "target") or default_target,
        workspace_root=workspace_root,
        requested_risk=_query_value(query, "risk"),
        reviewer_note=_query_value(query, "note") or default_note,
        expires_at=_query_value(query, "expires_at") or default_expires_at,
    )


def _render_app_html(dashboard_data: JsonMap) -> str:
    state_data = dashboard_data.get("state") if isinstance(dashboard_data.get("state"), dict) else {}
    preview_data = (
        dashboard_data.get("approval_preview") if isinstance(dashboard_data.get("approval_preview"), dict) else None
    )
    agent_packet_data = (
        dashboard_data.get("agent_packet") if isinstance(dashboard_data.get("agent_packet"), dict) else None
    )
    timeline = dashboard_data.get("timeline") if isinstance(dashboard_data.get("timeline"), dict) else {}
    active_request = (
        dashboard_data.get("active_request") if isinstance(dashboard_data.get("active_request"), dict) else None
    )
    request_cards = (
        dashboard_data.get("request_cards") if isinstance(dashboard_data.get("request_cards"), list) else []
    )
    command_center = (
        dashboard_data.get("command_center") if isinstance(dashboard_data.get("command_center"), list) else []
    )
    product_areas = (
        dashboard_data.get("product_areas") if isinstance(dashboard_data.get("product_areas"), list) else []
    )
    control_loop = (
        dashboard_data.get("control_loop") if isinstance(dashboard_data.get("control_loop"), list) else []
    )
    workspace_flow = (
        dashboard_data.get("workspace_flow") if isinstance(dashboard_data.get("workspace_flow"), dict) else {}
    )
    result_summary = (
        dashboard_data.get("result_summary") if isinstance(dashboard_data.get("result_summary"), dict) else {}
    )
    areas = _areas_by_id(product_areas)
    workspace = state_data.get("workspace") if isinstance(state_data.get("workspace"), dict) else {}
    ledger = state_data.get("ledger") if isinstance(state_data.get("ledger"), dict) else {}
    approval_inbox = ledger.get("approval_inbox") if isinstance(ledger.get("approval_inbox"), dict) else {}
    agents = state_data.get("agents") if isinstance(state_data.get("agents"), dict) else {}
    next_actions = dashboard_data.get("next_actions") if isinstance(dashboard_data.get("next_actions"), list) else []
    passports = agents.get("passports") if isinstance(agents.get("passports"), list) else []
    preview = preview_data or {}
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DelegationHQ Local App</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Inter, Segoe UI, Arial, sans-serif;
      background: #f7f7f4;
      color: #191919;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: #f7f7f4;
    }}
    header {{
      padding: 28px 32px 18px;
      border-bottom: 1px solid #d9d7cf;
      background: #ffffff;
    }}
    main {{
      max-width: 1160px;
      margin: 0 auto;
      padding: 24px 20px 40px;
    }}
    h1, h2, h3 {{
      margin: 0;
      letter-spacing: 0;
    }}
    h1 {{
      font-size: 32px;
      line-height: 1.1;
    }}
    h2 {{
      font-size: 18px;
      margin-bottom: 12px;
    }}
    p {{
      line-height: 1.5;
      margin: 6px 0 0;
    }}
    .subtle {{
      color: #5f625b;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
      margin: 18px 0;
    }}
    .panel {{
      background: #ffffff;
      border: 1px solid #dad8d0;
      border-radius: 8px;
      padding: 16px;
    }}
    .metric {{
      font-size: 26px;
      font-weight: 700;
      margin-top: 8px;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .metric-long {{
      font-size: 14px;
      line-height: 1.35;
      font-weight: 650;
    }}
    .command-block {{
      position: relative;
      margin-top: 8px;
    }}
    .copy-button, .refresh-button {{
      border: 1px solid #a9aaa2;
      border-radius: 6px;
      background: #ffffff;
      color: #222420;
      cursor: pointer;
      font: inherit;
      font-size: 12px;
      font-weight: 700;
      padding: 5px 8px;
    }}
    .copy-button {{
      position: absolute;
      top: 8px;
      right: 8px;
    }}
    .agent-passport {{
      border-top: 1px solid #e2e0d8;
      padding-top: 12px;
      margin-top: 12px;
    }}
    .agent-passport:first-child {{
      border-top: 0;
      padding-top: 0;
      margin-top: 0;
    }}
    .kv {{
      display: grid;
      gap: 6px;
      margin-top: 8px;
    }}
    .kv div {{
      overflow-wrap: anywhere;
    }}
    .action-panel, .form-grid {{
      border: 1px solid #e2e0d8;
      border-radius: 8px;
      padding: 12px;
      margin-top: 12px;
      background: #fbfbf8;
    }}
    .form-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 10px;
    }}
    label {{
      display: grid;
      gap: 4px;
      font-size: 12px;
      font-weight: 700;
      color: #3d403a;
    }}
    input, select, textarea {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #bbb9af;
      border-radius: 6px;
      background: #ffffff;
      color: #191919;
      font: inherit;
      font-size: 13px;
      padding: 8px;
    }}
    textarea {{
      min-height: 70px;
      resize: vertical;
    }}
    .action-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }}
    .action-button {{
      border: 1px solid #8f9188;
      border-radius: 6px;
      background: #222420;
      color: #ffffff;
      cursor: pointer;
      font: inherit;
      font-size: 13px;
      font-weight: 700;
      padding: 8px 10px;
    }}
    .action-button.secondary {{
      background: #ffffff;
      color: #222420;
    }}
    .app-message {{
      margin-top: 8px;
      font-size: 13px;
      color: #5f625b;
      overflow-wrap: anywhere;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border: 1px solid #b9b7ad;
      border-radius: 999px;
      padding: 4px 9px;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .ready {{ color: #116149; }}
    .attention {{ color: #8a4b00; }}
    .blocked {{ color: #9b1c1c; }}
    code {{
      display: block;
      white-space: pre-wrap;
      word-break: break-word;
      background: #20211f;
      color: #f3f3ed;
      padding: 10px;
      border-radius: 6px;
      font-size: 13px;
    }}
    ul {{
      padding-left: 18px;
    }}
    li {{
      margin: 6px 0;
    }}
    @media (max-width: 640px) {{
      header {{ padding: 22px 18px 14px; }}
      h1 {{ font-size: 26px; }}
      main {{ padding: 18px 14px 30px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>DelegationHQ Local App</h1>
    <p class="subtle">Local mission control for agentic work.</p>
    <p><button type="button" class="refresh-button" onclick="window.location.reload()">Refresh</button></p>
  </header>
  <main>
    <section class="grid" aria-label="Trust cockpit status">
      {_metric_panel("Workspace", workspace.get("status", "unknown"), workspace.get("root", "No workspace loaded"))}
      {_area_metric_panel(areas.get("missions"), "Missions", ledger.get("status", "unknown"))}
      {_area_metric_panel(areas.get("agents"), "Agents", agents.get("status", "unknown"))}
      {_area_metric_panel(areas.get("evidence"), "Evidence", "not_started")}
    </section>
    <section class="panel">
      <h2>Workspace Flow</h2>
      {_workspace_flow_html(workspace_flow)}
    </section>
    <section class="panel">
      <h2>Active Request</h2>
      {_active_request_html(active_request, request_cards, command_center)}
    </section>
    <section class="panel">
      <h2>Mission Result</h2>
      {_result_summary_html(result_summary)}
    </section>
    <section class="panel">
      <h2>Control Loop</h2>
      {_control_loop_html(control_loop)}
    </section>
    <section class="panel">
      <h2>Missions</h2>
      {_area_panel_html(areas.get("missions"))}
    </section>
    <section class="grid">
      <div class="panel">
        <h2>Agents</h2>
        {_agent_registration_form()}
        {_agents_html(passports, workspace.get("root", "."))}
      </div>
      <div class="panel">
        <h2>Approval Inbox</h2>
        {_area_panel_html(areas.get("approval_inbox"))}
        {_approval_inbox_cards_html(approval_inbox)}
        {_approval_preview_html(preview)}
      </div>
    </section>
    <section class="panel">
      <h2>Evidence</h2>
      {_area_panel_html(areas.get("evidence"))}
      {_agent_handoff_html(agent_packet_data, preview)}
    </section>
    <section class="panel">
      <h2>Timeline</h2>
      {_timeline_html(timeline)}
    </section>
    <section class="grid">
      <div class="panel">
        <h2>Settings</h2>
        {_settings_html(areas.get("settings"), command_center, workspace.get("root", "."), has_preview=bool(preview_data))}
      </div>
      <div class="panel">
        <h2>Next Actions</h2>
        {_next_actions_html(next_actions)}
      </div>
    </section>
  </main>
  <script id="delegation-dashboard" type="application/json">{_json_script(dashboard_data)}</script>
  <script id="delegation-state" type="application/json">{_json_script(state_data)}</script>
  <script id="delegation-timeline" type="application/json">{_json_script(timeline)}</script>
  <script id="delegation-active-request" type="application/json">{_json_script(active_request or {})}</script>
  <script id="delegation-approval-preview" type="application/json">{_json_script(preview_data or {})}</script>
  <script id="delegation-agent-packet" type="application/json">{_json_script(agent_packet_data or {})}</script>
  <script>
    document.addEventListener("click", async function (event) {{
      const button = event.target.closest("[data-copy]");
      if (!button) return;
      const target = document.getElementById(button.getAttribute("data-copy"));
      if (!target) return;
      const text = target.textContent || "";
      try {{
        await navigator.clipboard.writeText(text);
        button.textContent = "Copied";
        window.setTimeout(function () {{ button.textContent = "Copy"; }}, 1200);
      }} catch (error) {{
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(target);
        selection.removeAllRanges();
        selection.addRange(range);
        button.textContent = "Selected";
      }}
    }});
    document.addEventListener("click", async function (event) {{
      const button = event.target.closest("[data-approval-decision]");
      if (!button) return;
      const panel = button.closest("[data-active-request-controls], [data-inbox-request-controls]");
      if (!panel) return;
      const payload = {{
        action_id: panel.getAttribute("data-action-id") || "",
        decision: button.getAttribute("data-approval-decision") || "",
        approver: panel.querySelector("[data-approval-approver]")?.value || "",
        reason: panel.querySelector("[data-approval-reason]")?.value || "",
        confirm: panel.querySelector("[data-local-write-confirm]")?.value || ""
      }};
      await postDelegationAction("/api/approval-decision", payload, panel);
    }});
    document.addEventListener("click", async function (event) {{
      const button = event.target.closest("[data-agent-register]");
      if (!button) return;
      const panel = button.closest("[data-agent-form]");
      if (!panel) return;
      const endpointType = panel.querySelector("[data-agent-endpoint-type]")?.value || "command";
      const payload = {{
        agent_id: panel.querySelector("[data-agent-id]")?.value || "",
        name: panel.querySelector("[data-agent-name]")?.value || "",
        runtime_type: panel.querySelector("[data-agent-runtime]")?.value || "cli.command",
        capabilities: panel.querySelector("[data-agent-capabilities]")?.value || "",
        allowed_data: panel.querySelector("[data-agent-allowed-data]")?.value || "",
        approvals: panel.querySelector("[data-agent-approvals]")?.value || "",
        evidence: panel.querySelector("[data-agent-evidence]")?.value || "",
        confirm: panel.querySelector("[data-local-write-confirm]")?.value || "",
        force: panel.querySelector("[data-agent-force]")?.checked || false
      }};
      payload.command = endpointType === "command" ? panel.querySelector("[data-agent-endpoint]")?.value || "" : "";
      payload.api_url = endpointType === "api" ? panel.querySelector("[data-agent-endpoint]")?.value || "" : "";
      payload.webhook_url = endpointType === "webhook" ? panel.querySelector("[data-agent-endpoint]")?.value || "" : "";
      payload.mcp_endpoint = endpointType === "mcp" ? panel.querySelector("[data-agent-endpoint]")?.value || "" : "";
      await postDelegationAction("/api/agent-add", payload, panel);
    }});
    async function postDelegationAction(url, payload, panel) {{
      const target = panel.querySelector("[data-app-message]");
      if (target) target.textContent = "Working...";
      try {{
        const response = await fetch(url, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload)
        }});
        const data = await response.json();
        if (target) target.textContent = data.message || data.status || "Done.";
        if (response.ok) {{
          window.setTimeout(function () {{ window.location.reload(); }}, 900);
        }}
      }} catch (error) {{
        if (target) target.textContent = "Could not reach the local action server. Start with --allow-actions.";
      }}
    }}
  </script>
</body>
</html>
"""


def _metric_panel(title: str, value: T.Any, detail: T.Any) -> str:
    status_class = _status_class(str(value))
    detail_text = str(detail)
    detail_class = "metric metric-long" if len(detail_text) > 42 else "metric"
    return f"""<div class="panel">
  <h2>{_escape(title)}</h2>
  <span class="badge {status_class}">{_escape(value)}</span>
  <div class="{detail_class}" title="{_escape(detail_text)}">{_escape(detail_text)}</div>
</div>"""


def _area_metric_panel(area: JsonMap | None, title: str, fallback_status: T.Any) -> str:
    if not area:
        return _metric_panel(title, fallback_status, "No live data yet")
    return _metric_panel(area.get("title", title), area.get("status", fallback_status), area.get("summary", ""))


def _area_panel_html(area: JsonMap | None) -> str:
    if not area:
        return "<p class=\"subtle\">No live data yet.</p>"
    metrics = area.get("metrics") if isinstance(area.get("metrics"), dict) else {}
    metric_rows = "".join(
        f"<div><strong>{_escape(_labelize(key))}:</strong> {_escape(value)}</div>"
        for key, value in metrics.items()
    )
    next_action = area.get("next_action")
    next_html = (
        '<p class="subtle">Next</p>'
        + _copyable_code(next_action, id_hint=f"area-{area.get('id', 'next')}")
        if isinstance(next_action, str) and next_action.strip()
        else ""
    )
    return f"""<p><strong>{_escape(area.get("summary", "No summary available."))}</strong></p>
<div class="kv">
  <div><strong>Status:</strong> {_escape(area.get("status", "unknown"))}</div>
  {metric_rows}
</div>
{next_html}"""


def _active_request_html(
    active_request: JsonMap | None,
    request_cards: list[T.Any],
    commands: list[T.Any],
) -> str:
    if not active_request:
        return (
            "<p class=\"subtle\">No real action request is active yet.</p>"
            "<p class=\"subtle\">When a registered agent submits a request, it appears here before execution.</p>"
        )
    summary = active_request.get("request_summary") or active_request.get("title") or "Action request"
    action_id = active_request.get("action_id", "unknown")
    status = active_request.get("status", "unknown")
    requested_by = active_request.get("requested_by") or active_request.get("agent_id") or "unknown"
    risk = active_request.get("risk", "unknown")
    action = active_request.get("action", "unknown")
    target = active_request.get("target", "unknown")
    relevant_commands = [
        command
        for command in commands
        if isinstance(command, dict)
        and command.get("id") in {"approve_request", "block_request", "request_status", "request_run", "export_agent_packet"}
    ]
    queue_count = len([item for item in request_cards if isinstance(item, dict)])
    return f"""
<p><strong>{_escape(summary)}</strong></p>
<div class="grid">
  {_metric_panel("Status", status, f"risk: {risk}")}
  {_metric_panel("Agent", requested_by, f"{action} -> {target}")}
  {_metric_panel("Action", action_id, f"{queue_count} request card(s) in workspace")}
</div>
<p class="subtle">Operator commands</p>
{_commands_html(relevant_commands, section_id="active-request-commands")}
{_approval_action_controls(action_id, status, panel_id="active")}
"""


def _control_loop_html(steps: list[T.Any]) -> str:
    if not steps:
        return "<p class=\"subtle\">No control loop data yet.</p>"
    rows: list[str] = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        title = step.get("title", f"Step {index}")
        status = step.get("status", "unknown")
        summary = step.get("summary", "")
        next_action = step.get("next_action")
        command_html = (
            _copyable_code(next_action, id_hint=f"control-loop-{index}")
            if isinstance(next_action, str) and next_action.strip()
            else ""
        )
        rows.append(
            "<li>"
            f"<strong>{_escape(index)}. {_escape(title)}</strong> "
            f"<span class=\"badge {_status_class(str(status))}\">{_escape(status)}</span>"
            + (f"<p class=\"subtle\">{_escape(summary)}</p>" if summary else "")
            + command_html
            + "</li>"
        )
    return "<ul>" + "".join(rows) + "</ul>" if rows else "<p class=\"subtle\">No readable control loop data.</p>"


def _approval_preview_html(preview: JsonMap) -> str:
    if not preview:
        return "<p class=\"subtle\">No agent passport is available yet.</p>"
    context = preview.get("request_context") if isinstance(preview.get("request_context"), dict) else {}
    resource = preview.get("resource_summary") if isinstance(preview.get("resource_summary"), dict) else {}
    evidence = preview.get("evidence_status") if isinstance(preview.get("evidence_status"), dict) else {}
    intent = preview.get("action_intent") if isinstance(preview.get("action_intent"), dict) else {}
    history = preview.get("history") if isinstance(preview.get("history"), dict) else {}
    return f"""
<p><strong>{_escape(preview.get("summary", "No summary available."))}</strong></p>
<div class="grid">
  {_metric_panel("Decision", preview.get("decision", "unknown"), f"risk: {preview.get('risk', 'unknown')}")}
  {_metric_panel("Agent", preview.get("agent_id", "unknown"), preview.get("action", "unknown"))}
  {_metric_panel("History", history.get("status", "unknown"), history.get("summary", "No history loaded."))}
  {_metric_panel("Evidence", evidence.get("status", "unknown"), evidence.get("summary", "No evidence summary."))}
</div>
<p class="subtle">Request packet</p>
{_request_packet_html(context, preview)}
<p class="subtle">Touched resources</p>
{_resource_summary_html(resource)}
<p class="subtle">Action intent</p>
{_action_intent_html(intent)}
<p class="subtle">Required approvals</p>
{_list_html(preview.get("required_approvals") if isinstance(preview.get("required_approvals"), list) else [])}
<p class="subtle">Required evidence</p>
{_list_html(preview.get("required_evidence") if isinstance(preview.get("required_evidence"), list) else [])}
<p class="subtle">Decision history</p>
{_approval_history_html(history)}
<p class="subtle">Safe next step</p>
<p>{_escape(preview.get("safe_next_step", "Review the request before continuing."))}</p>
<p class="subtle">Decision commands</p>
{_commands_html(preview.get("decision_commands") if isinstance(preview.get("decision_commands"), list) else [], section_id="approval-commands")}
"""


def _workspace_flow_html(flow: JsonMap) -> str:
    steps = flow.get("steps") if isinstance(flow.get("steps"), list) else []
    if not steps:
        return "<p class=\"subtle\">No guided flow is available yet.</p>"
    rows: list[str] = []
    current = flow.get("current_step") if isinstance(flow.get("current_step"), str) else ""
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        step_id = step.get("id", "")
        title = step.get("title", "Step")
        status = step.get("status", "unknown")
        summary = step.get("summary", "")
        command = step.get("command", "")
        marker = "Current" if step_id == current else "Done" if step.get("done") else "Waiting"
        rows.append(
            "<li>"
            f"<strong>{_escape(index)}. {_escape(title)}</strong> "
            f"<span class=\"badge {_status_class(str(status))}\">{_escape(status)}</span> "
            f"<span class=\"subtle\">{_escape(marker)}</span>"
            + (f"<p class=\"subtle\">{_escape(summary)}</p>" if summary else "")
            + (_copyable_code(command, id_hint=f"workspace-flow-{index}") if isinstance(command, str) and command else "")
            + "</li>"
        )
    next_command = flow.get("next_command") if isinstance(flow.get("next_command"), str) else ""
    return (
        f"<p><strong>{_escape(flow.get('status', 'unknown'))}</strong> "
        f"<span class=\"subtle\">Current: {_escape(current or 'complete')}</span></p>"
        "<ul>"
        + "".join(rows)
        + "</ul>"
        + ("<p class=\"subtle\">Next safe command</p>" + _copyable_code(next_command, id_hint="workspace-flow-next") if next_command else "")
    )


def _approval_inbox_cards_html(inbox: JsonMap) -> str:
    items = inbox.get("items") if isinstance(inbox.get("items"), list) else []
    if not items:
        return "<p class=\"subtle\">No submitted action requests yet.</p>"
    ledger_source = inbox.get("ledger_source") if isinstance(inbox.get("ledger_source"), str) else "LEDGER"
    rows: list[str] = []
    for index, item in enumerate(items[:6], start=1):
        if not isinstance(item, dict):
            continue
        action_id = item.get("action_id", "unknown")
        requested_by = item.get("requested_by") or item.get("agent_id", "unknown")
        summary = item.get("request_summary") or item.get("title", "Action request")
        status = item.get("status", "unknown")
        risk = item.get("risk", "unknown")
        evidence = _inline_list(item.get("required_evidence")) or "not declared"
        approvals = _inline_list(item.get("required_approvals")) or "none"
        next_action = _inbox_card_next_action(item, ledger_source=ledger_source)
        rows.append(
            "<li>"
            f"<strong>{_escape(index)}. {_escape(summary)}</strong> "
            f"<span class=\"badge {_status_class(str(status))}\">{_escape(status)}</span>"
            "<div class=\"kv\">"
            f"<div><strong>Requested by:</strong> {_escape(requested_by)}</div>"
            f"<div><strong>Action:</strong> {_escape(action_id)}</div>"
            f"<div><strong>Risk:</strong> {_escape(risk)}</div>"
            f"<div><strong>Approvals:</strong> {_escape(approvals)}</div>"
            f"<div><strong>Evidence:</strong> {_escape(evidence)}</div>"
            "</div>"
            + _approval_action_controls(str(action_id), str(status), panel_id=f"inbox-{index}")
            + (
                "<p class=\"subtle\">Next</p>"
                + _copyable_code(next_action, id_hint=f"approval-inbox-card-{index}")
                if isinstance(next_action, str) and next_action.strip()
                else ""
            )
            + "</li>"
        )
    return "<p class=\"subtle\">Submitted action requests</p><ul>" + "".join(rows) + "</ul>"


def _inbox_card_next_action(item: JsonMap, *, ledger_source: str) -> str:
    status = item.get("status")
    action_id = item.get("action_id")
    if not isinstance(action_id, str) or not action_id.strip():
        return str(item.get("next_action", ""))
    if status == "pending_approval":
        return f"delegation approval-decision --ledger {ledger_source} --action-id {action_id} --decision approve --approver NAME"
    if status in {"approved", "needs_evidence", "ready_for_recording"}:
        return f"delegation request-run --ledger {ledger_source} --action-id {action_id} --confirm LOCAL_AGENT_EXECUTION"
    if status == "recorded":
        return f"delegation request-status --ledger {ledger_source} --action-id {action_id}"
    value = item.get("next_action", "")
    return value if isinstance(value, str) else ""


def _approval_action_controls(action_id: str, status: str, *, panel_id: str) -> str:
    if status not in {"pending_approval", "warning"} or not action_id or action_id == "unknown":
        return ""
    attr_action = _escape(action_id)
    return f"""
<div class="action-panel" data-{_escape(panel_id)}-request-controls data-inbox-request-controls data-action-id="{attr_action}">
  <p class="subtle">Guarded local decision</p>
  <div class="form-grid">
    <label>Approver
      <input data-approval-approver autocomplete="name" placeholder="Your name">
    </label>
    <label>Confirmation
      <input data-local-write-confirm placeholder="{LOCAL_APP_WRITE_CONFIRMATION}">
    </label>
    <label>Reason
      <input data-approval-reason placeholder="Optional reason">
    </label>
  </div>
  <div class="action-row">
    <button type="button" class="action-button" data-approval-decision="approve">Approve</button>
    <button type="button" class="action-button secondary" data-approval-decision="block">Block</button>
  </div>
  <div class="app-message" data-app-message>Requires app-serve --allow-actions and {LOCAL_APP_WRITE_CONFIRMATION}.</div>
</div>"""


def _agent_registration_form() -> str:
    return f"""
<div class="action-panel" data-agent-form>
  <p><strong>Add Agent Passport</strong></p>
  <p class="subtle">Register a CLI/API/webhook/MCP worker under DelegationHQ control.</p>
  <div class="form-grid">
    <label>Agent id
      <input data-agent-id placeholder="research_agent">
    </label>
    <label>Name
      <input data-agent-name placeholder="Research Agent">
    </label>
    <label>Runtime
      <select data-agent-runtime>
        <option value="cli.command">CLI command</option>
        <option value="api.http">API HTTP</option>
        <option value="webhook">Webhook</option>
        <option value="mcp.tool">MCP tool/workflow</option>
      </select>
    </label>
    <label>Endpoint type
      <select data-agent-endpoint-type>
        <option value="command">Command</option>
        <option value="api">API URL</option>
        <option value="webhook">Webhook URL</option>
        <option value="mcp">MCP endpoint</option>
      </select>
    </label>
    <label>Endpoint
      <input data-agent-endpoint placeholder="python agents/research_agent.py">
    </label>
    <label>Capabilities
      <input data-agent-capabilities value="read.workspace">
    </label>
    <label>Allowed data
      <input data-agent-allowed-data value="workspace">
    </label>
    <label>Approval rules
      <input data-agent-approvals placeholder="write.workspace">
    </label>
    <label>Evidence required
      <input data-agent-evidence value="command_output">
    </label>
    <label>Confirmation
      <input data-local-write-confirm placeholder="{LOCAL_APP_WRITE_CONFIRMATION}">
    </label>
    <label>Replace existing
      <input type="checkbox" data-agent-force>
    </label>
  </div>
  <div class="action-row">
    <button type="button" class="action-button" data-agent-register>Register Agent</button>
  </div>
  <div class="app-message" data-app-message>Requires app-serve --allow-actions and {LOCAL_APP_WRITE_CONFIRMATION}.</div>
</div>"""


def _result_summary_html(summary: JsonMap) -> str:
    if not summary:
        return "<p class=\"subtle\">No result summary is available yet.</p>"
    latest = summary.get("latest_items") if isinstance(summary.get("latest_items"), list) else []
    latest_rows = []
    for item in latest:
        if not isinstance(item, dict):
            continue
        label = f"{item.get('sequence', '?')}. [{item.get('stage', 'ledger')}] {item.get('status', 'unknown')}"
        latest_rows.append(
            "<li>"
            f"<strong>{_escape(label)}</strong> {_escape(item.get('title', 'event'))}"
            + (" <span class=\"badge attention\">attention</span>" if item.get("needs_attention") else "")
            + "</li>"
        )
    latest_html = "<ul>" + "".join(latest_rows) + "</ul>" if latest_rows else "<p class=\"subtle\">No recent events yet.</p>"
    return f"""
<p><strong>{_escape(summary.get("summary", "No result yet."))}</strong></p>
<div class="grid">
  {_metric_panel("Result", summary.get("status", "unknown"), f"active: {summary.get('active_request_status', 'none')}")}
  {_metric_panel("Evidence", summary.get("evidence_count", 0), f"records: {summary.get('record_events', 0)}")}
  {_metric_panel("Timeline", summary.get("timeline_events", 0), f"attention: {summary.get('attention_count', 0)}")}
  {_metric_panel("Execution", summary.get("execute_events", 0), f"packet: {summary.get('agent_packet_status', 'missing')}")}
</div>
<p class="subtle">Latest proof trail</p>
{latest_html}
"""


def _agent_handoff_html(packet_report: JsonMap | None, preview: JsonMap) -> str:
    action_id = preview.get("action_id") if isinstance(preview.get("action_id"), str) else "ACTION_ID"
    ledger = preview.get("ledger") if isinstance(preview.get("ledger"), str) else ".delegation/run.jsonl"
    export_command = f"delegation agent-packet --ledger {ledger} --action-id {action_id} --output .delegation/agent-packet.json"
    ingest_command = f"delegation agent-result-ingest --ledger {ledger} --action-id {action_id} --result .delegation/agent-result.json"
    if not packet_report:
        return f"""
<p><strong>No Agent Packet is available yet.</strong></p>
<p class="subtle">First record an Agent Gate receipt, then export the worker job card.</p>
<div class="grid">
  {_metric_panel("Packet", "missing", "record a gate receipt first")}
  {_metric_panel("Return", "waiting", "agent-result.json")}
</div>
<p class="subtle">Export packet</p>
{_copyable_code(export_command, id_hint="agent-handoff-export-missing")}
<p class="subtle">Ingest result</p>
{_copyable_code(ingest_command, id_hint="agent-handoff-ingest-missing")}
"""
    packet = packet_report.get("packet") if isinstance(packet_report.get("packet"), dict) else {}
    agent = packet.get("agent") if isinstance(packet.get("agent"), dict) else {}
    work = packet.get("requested_work") if isinstance(packet.get("requested_work"), dict) else {}
    controls = packet.get("required_controls") if isinstance(packet.get("required_controls"), dict) else {}
    receipts = packet.get("current_receipts") if isinstance(packet.get("current_receipts"), dict) else {}
    return_contract = packet.get("return_contract") if isinstance(packet.get("return_contract"), dict) else {}
    if isinstance(return_contract.get("ingest_command"), str) and return_contract["ingest_command"].strip():
        ingest_command = return_contract["ingest_command"].strip()
    evidence_ingest_command = (
        return_contract.get("evidence_ingest_command")
        if isinstance(return_contract.get("evidence_ingest_command"), str)
        else ""
    )
    evidence_command_html = (
        _copyable_code(evidence_ingest_command, id_hint="agent-handoff-evidence-ingest")
        if evidence_ingest_command
        else '<p class="subtle">Use evidence-ingest after a recorder or workflow produces proof.</p>'
    )
    warnings = packet_report.get("warnings") if isinstance(packet_report.get("warnings"), list) else []
    return f"""
<p><strong>Packet status: {_escape(packet_report.get("status", "unknown"))}</strong></p>
<div class="grid">
  {_metric_panel("Agent", agent.get("id", "unknown"), agent.get("runtime_type", "unknown"))}
  {_metric_panel("Work", work.get("action", "unknown"), work.get("target", "unknown"))}
  {_metric_panel("Execute", str(packet.get("can_execute", False)).lower(), f"gate: {work.get('gate_decision', 'unknown')}")}
  {_metric_panel("Evidence", str(receipts.get("runprint_recorded", False)).lower(), _inline_list(controls.get("evidence")) or "none")}
</div>
<p class="subtle">Required approvals</p>
{_list_html(controls.get("approvals") if isinstance(controls.get("approvals"), list) else [])}
<p class="subtle">Return contract</p>
{_return_contract_html(return_contract)}
<p class="subtle">Warnings</p>
{_list_html(warnings)}
<p class="subtle">Export packet</p>
{_copyable_code(export_command, id_hint="agent-handoff-export")}
<p class="subtle">Ingest result</p>
{_copyable_code(ingest_command, id_hint="agent-handoff-ingest")}
<p class="subtle">Attach external evidence</p>
{evidence_command_html}
"""


def _return_contract_html(contract: JsonMap) -> str:
    if not contract:
        return "<p class=\"subtle\">No return contract found.</p>"
    fields = contract.get("must_return") if isinstance(contract.get("must_return"), list) else []
    statuses = contract.get("allowed_statuses") if isinstance(contract.get("allowed_statuses"), list) else []
    schema = contract.get("schema_version", "unknown")
    ingest = contract.get("ingest_command") if isinstance(contract.get("ingest_command"), str) else ""
    evidence_ingest = (
        contract.get("evidence_ingest_command") if isinstance(contract.get("evidence_ingest_command"), str) else ""
    )
    return f"""<div class="kv">
  <div><strong>Schema:</strong> {_escape(schema)}</div>
  <div><strong>Fields:</strong> {_escape(_inline_list(fields) or "none")}</div>
  <div><strong>Statuses:</strong> {_escape(_inline_list(statuses) or "none")}</div>
  <div><strong>Result ingest:</strong> {_escape(ingest or "not declared")}</div>
  <div><strong>Evidence ingest:</strong> {_escape(evidence_ingest or "not declared")}</div>
</div>"""


def _agents_html(passports: list[T.Any], workspace_root: T.Any) -> str:
    if not passports:
        return "<p class=\"subtle\">No agents registered yet.</p>"
    rows = []
    for item in passports[:8]:
        if not isinstance(item, dict):
            continue
        rows.append(_agent_passport_html(item, workspace_root=workspace_root))
    return "".join(rows) if rows else "<p class=\"subtle\">No readable passports found.</p>"


def _timeline_html(timeline: JsonMap) -> str:
    items = timeline.get("items") if isinstance(timeline.get("items"), list) else []
    if not items:
        return "<p class=\"subtle\">No timeline events yet.</p>"
    rows: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        sequence = item.get("sequence")
        prefix = f"{sequence}. " if isinstance(sequence, int) else ""
        attention = " needs attention" if item.get("needs_attention") else ""
        title = item.get("title", "event")
        stage = item.get("stage", "ledger")
        status = item.get("status", "unknown")
        message = item.get("message", "")
        rows.append(
            "<li>"
            f"<strong>{_escape(prefix)}[{_escape(stage)}] {_escape(status)}</strong> "
            f"{_escape(title)}{_escape(attention)}"
            + (f"<p class=\"subtle\">{_escape(message)}</p>" if message else "")
            + "</li>"
        )
    event_count = timeline.get("event_count", len(items))
    return f"<p class=\"subtle\">Showing {len(items)} of {_escape(event_count)} event(s).</p><ul>" + "".join(rows) + "</ul>"


def _commands_html(commands: list[T.Any], *, section_id: str = "commands") -> str:
    if not commands:
        return "<p class=\"subtle\">none</p>"
    rows: list[str] = []
    for index, item in enumerate(commands[:8], start=1):
        if not isinstance(item, dict):
            continue
        label = item.get("label", "Command")
        command = item.get("command", "")
        purpose = item.get("purpose", "")
        rows.append(
            "<li>"
            f"<strong>{_escape(label)}</strong>"
            + (f"<p class=\"subtle\">{_escape(purpose)}</p>" if purpose else "")
            + (_copyable_code(command, id_hint=f"{section_id}-{index}") if command else "")
            + "</li>"
        )
    return "<ul>" + "".join(rows) + "</ul>"


def _next_actions_html(actions: list[T.Any]) -> str:
    if not actions:
        return "<p class=\"subtle\">none</p>"
    rows: list[str] = []
    for index, action in enumerate(actions[:8], start=1):
        if not isinstance(action, str) or not action.strip():
            continue
        label, purpose = _describe_next_action(action)
        rows.append(
            "<li>"
            f"<strong>{_escape(label)}</strong>"
            f"<p class=\"subtle\">{_escape(purpose)}</p>"
            f"{_copyable_code(action, id_hint=f'next-action-{index}')}"
            "</li>"
        )
    return "<ul>" + "".join(rows) + "</ul>" if rows else "<p class=\"subtle\">none</p>"


def _request_packet_html(context: JsonMap, preview: JsonMap) -> str:
    note = context.get("reviewer_note") or preview.get("reviewer_note") or "none"
    expires = context.get("expires_at") or preview.get("expires_at") or "not set"
    expired = context.get("expired") or preview.get("expired")
    expiry_status = "expired" if expired else "active"
    return f"""<div class="kv">
  <div><strong>Intent:</strong> {_escape(context.get("intent", "unknown"))}</div>
  <div><strong>Operation:</strong> {_escape(context.get("operation", preview.get("action", "unknown")))}</div>
  <div><strong>Decision reason:</strong> {_escape(context.get("decision_reason", "unknown"))}</div>
  <div><strong>Reviewer note:</strong> {_escape(note)}</div>
  <div><strong>Expires:</strong> {_escape(expires)} ({_escape(expiry_status)})</div>
</div>"""


def _resource_summary_html(resource: JsonMap) -> str:
    touches = resource.get("touches") if isinstance(resource.get("touches"), list) else []
    return f"""<div class="kv">
  <div><strong>Target:</strong> {_escape(resource.get("target", "unknown"))}</div>
  <div><strong>Kind:</strong> {_escape(resource.get("target_kind", "unknown"))}</div>
  <div><strong>Endpoint:</strong> {_escape(resource.get("endpoint", "unknown"))}</div>
  <div><strong>Scope:</strong> {_escape(_inline_list(touches) or "not declared")}</div>
  <div><strong>Action check:</strong> {_escape(resource.get("matched_action_check", "not checked"))}</div>
  <div><strong>Target check:</strong> {_escape(resource.get("matched_target_check", "not checked"))}</div>
</div>"""


def _action_intent_html(intent: JsonMap) -> str:
    if not intent:
        return "<p class=\"subtle\">No action intent preview found.</p>"
    command = intent.get("command_preview") if isinstance(intent.get("command_preview"), dict) else {}
    resources = intent.get("resource_preview") if isinstance(intent.get("resource_preview"), dict) else {}
    change = intent.get("change_preview") if isinstance(intent.get("change_preview"), dict) else {}
    likely_touches = resources.get("likely_touches") if isinstance(resources.get("likely_touches"), list) else []
    evidence = intent.get("evidence_to_collect") if isinstance(intent.get("evidence_to_collect"), list) else []
    command_html = ""
    if isinstance(command.get("command"), str) and command["command"].strip():
        command_html = _copyable_code(command["command"], id_hint="action-intent-command")
    return f"""<div class="kv">
  <div><strong>Mode:</strong> {_escape(intent.get("execution_mode", "unknown"))}</div>
  <div><strong>Live effect:</strong> {_escape(intent.get("live_effect", "unknown"))}</div>
  <div><strong>Workspace effect:</strong> {_escape(intent.get("workspace_effect", "unknown"))}</div>
  <div><strong>Confirmation:</strong> {_escape(intent.get("confirmation", "unknown"))}</div>
  <div><strong>Human question:</strong> {_escape(intent.get("human_question", "Review this request before continuing."))}</div>
  <div><strong>Likely touches:</strong> {_escape(_inline_list(likely_touches) or "not declared")}</div>
  <div><strong>Proof needed:</strong> {_escape(_inline_list(evidence) or "not declared")}</div>
  <div><strong>Change preview:</strong> {_escape(change.get("summary", "not available"))}</div>
</div>{command_html}"""


def _approval_history_html(history: JsonMap) -> str:
    recent = history.get("recent_events") if isinstance(history.get("recent_events"), list) else []
    rows = [
        f"<div><strong>Status:</strong> {_escape(history.get('status', 'unknown'))}</div>",
        f"<div><strong>Summary:</strong> {_escape(history.get('summary', 'No history loaded.'))}</div>",
        f"<div><strong>Gate receipts:</strong> {_escape(history.get('gate_count', 0))}</div>",
        f"<div><strong>Recorded proof:</strong> {_escape(history.get('recorded_count', 0))}</div>",
        f"<div><strong>Approvals:</strong> {_escape(history.get('approval_count', 0))}</div>",
        f"<div><strong>Blocks:</strong> {_escape(history.get('block_count', 0))}</div>",
    ]
    if recent:
        rows.append("<div><strong>Recent:</strong></div>")
        for item in recent[-3:]:
            if isinstance(item, dict):
                rows.append(
                    "<div>"
                    f"{_escape(item.get('sequence', '?'))}. {_escape(item.get('event_type', 'event'))} "
                    f"[{_escape(item.get('status', 'unknown'))}]"
                    "</div>"
                )
    return "<div class=\"kv\">" + "".join(rows) + "</div>"


def _agent_passport_html(passport: JsonMap, *, workspace_root: T.Any) -> str:
    agent_id = passport.get("id", "unknown")
    runtime = passport.get("runtime_type", "unknown")
    autonomy = passport.get("autonomy_level", "unknown")
    risk = passport.get("risk_level", "unknown")
    source = passport.get("source", "unknown")
    endpoint = _endpoint_summary(passport.get("endpoint"))
    capabilities = _inline_list(passport.get("capabilities"))
    allowed_tools = _inline_list(passport.get("allowed_tools"))
    allowed_data = _inline_list(passport.get("allowed_data"))
    approvals = _inline_list(passport.get("required_approvals")) or "none"
    evidence = _inline_list(passport.get("evidence_requirements")) or "none"
    outputs = _inline_list(passport.get("expected_outputs")) or "not declared"
    promotion = _inline_list(passport.get("promotion_evals")) or "none"
    warnings = _inline_list(passport.get("warnings"))
    preview_command = f"delegation approval-preview {agent_id} --workspace {workspace_root}"
    return f"""<div class="agent-passport">
  <h3>{_escape(agent_id)}</h3>
  <div class="kv">
    <div><strong>Runtime:</strong> {_escape(runtime)}</div>
    <div><strong>Endpoint:</strong> {_escape(endpoint)}</div>
    <div><strong>Source:</strong> {_escape(source)}</div>
    <div><strong>Trust:</strong> autonomy {_escape(autonomy)}, risk {_escape(risk)}</div>
    <div><strong>Can do:</strong> {_escape(capabilities or "no capabilities declared")}</div>
    <div><strong>Can use:</strong> {_escape(allowed_tools or "no tool scope declared")}</div>
    <div><strong>Can touch:</strong> {_escape(allowed_data or "no data scope declared")}</div>
    <div><strong>Approvals:</strong> {_escape(approvals)}</div>
    <div><strong>Evidence:</strong> {_escape(evidence)}</div>
    <div><strong>Outputs:</strong> {_escape(outputs)}</div>
    <div><strong>Promotion evals:</strong> {_escape(promotion)}</div>
    <div><strong>Warnings:</strong> {_escape(warnings or "none")}</div>
  </div>
  <p class="subtle">Preview this agent</p>
  {_copyable_code(preview_command, id_hint=f"agent-preview-{agent_id}")}
</div>"""


def _settings_html(
    settings: JsonMap | None,
    commands: list[T.Any],
    workspace_root: T.Any,
    *,
    has_preview: bool,
) -> str:
    rows = [_area_panel_html(settings)]
    refresh = _command_by_id(commands, "refresh_dashboard")
    timeline = _command_by_id(commands, "timeline")
    settings_commands = [command for command in (refresh, timeline) if command]
    if settings_commands:
        rows.append("<p class=\"subtle\">Safe commands</p>")
        rows.append(_commands_html(settings_commands, section_id="settings-commands"))
    rows.append("<p class=\"subtle\">Local data</p>")
    rows.append(_local_data_html(workspace_root, has_preview=has_preview))
    return "".join(rows)


def _local_data_html(workspace_root: T.Any, *, has_preview: bool) -> str:
    command = f"delegation app-state --workspace {workspace_root} --json"
    preview_link = (
        '  <li><a href="approval-preview.json">approval-preview.json</a> - current human approval card.</li>'
        if has_preview
        else "  <li>approval-preview.json - created after an Agent Passport is selected.</li>"
    )
    return f"""
<p class="subtle">This workspace runs local-first. GitHub is an adapter, not the core.</p>
<ul>
  <li><a href="dashboard.json">dashboard.json</a> - one-screen app brain.</li>
  <li><a href="state.json">state.json</a> - workspace health, agents, ledger, and guardrails.</li>
  <li><a href="timeline.json">timeline.json</a> - full mission proof trail.</li>
{preview_link}
</ul>
{_copyable_code(command, id_hint="local-data-state")}
"""


def _areas_by_id(areas: list[T.Any]) -> dict[str, JsonMap]:
    result: dict[str, JsonMap] = {}
    for area in areas:
        if isinstance(area, dict) and isinstance(area.get("id"), str) and area["id"].strip():
            result[area["id"].strip()] = area
    return result


def _command_by_id(commands: list[T.Any], command_id: str) -> JsonMap | None:
    for command in commands:
        if isinstance(command, dict) and command.get("id") == command_id:
            return command
    return None


def _labelize(value: T.Any) -> str:
    text = str(value).replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else ""


def _copyable_code(value: T.Any, *, id_hint: str) -> str:
    text = str(value)
    digest = hashlib.sha256(f"{id_hint}:{text}".encode("utf-8")).hexdigest()[:10]
    element_id = f"copy-{_dom_id(id_hint)}-{digest}"
    return (
        f"<div class=\"command-block\">"
        f"<button type=\"button\" class=\"copy-button\" data-copy=\"{element_id}\">Copy</button>"
        f"<code id=\"{element_id}\">{_escape(text)}</code>"
        f"</div>"
    )


def _list_html(values: T.Sequence[T.Any]) -> str:
    if not values:
        return "<p class=\"subtle\">none</p>"
    return "<ul>" + "".join(f"<li>{_escape(value)}</li>" for value in values) + "</ul>"


def _describe_next_action(action: str) -> tuple[str, str]:
    lowered = action.lower()
    command_text = lowered.strip()
    if "app-dashboard" in command_text:
        return "Refresh dashboard", "Reload the combined app state."
    if "approval-preview" in command_text:
        return "Preview approval", "Recheck the agent request before action."
    if command_text.startswith("delegation timeline") or " delegation timeline " in command_text:
        return "Review timeline", "Inspect the mission proof trail."
    if command_text.startswith("delegation agent-run") or " delegation agent-run " in command_text:
        return "Run gated agent", "Execute only after Agent Gate allows it and confirmation is present."
    if command_text.startswith("delegation agent-packet") or " delegation agent-packet " in command_text:
        return "Export agent packet", "Create the job card for a custom agent."
    if command_text.startswith("delegation agent-result-ingest") or " delegation agent-result-ingest " in command_text:
        return "Ingest agent result", "Check the worker result and append proof to the ledger."
    if command_text.startswith("delegation plan") or " delegation plan " in command_text:
        return "Refresh plan", "Rebuild the dry-run mission plan."
    if command_text.startswith("delegation agents") or " delegation agents " in command_text:
        return "Review agents", "Inspect Agent Passports and trust settings."
    if command_text.startswith("delegation cockpit") or " delegation cockpit " in command_text:
        return "View cockpit state", "Print the workspace state in the terminal."
    if "scripts/qa.py" in command_text:
        return "Run QA", "Verify the full local quality gate."
    if "package_smoke.py" in command_text:
        return "Run package smoke", "Verify the installable package path."
    if command_text.startswith("run evals"):
        return "Run evals", "Judge the recorded evidence before promotion."
    return "Next command", "Suggested next step from DelegationHQ."


def _inline_list(value: T.Any) -> str:
    if not isinstance(value, list):
        return ""
    return ", ".join(str(item) for item in value if isinstance(item, str) and item.strip())


def _endpoint_summary(value: T.Any) -> str:
    if not isinstance(value, dict):
        return "not declared"
    endpoint_type = value.get("type", "unknown")
    endpoint_value = value.get("value", "")
    if endpoint_value:
        return f"{endpoint_type}: {endpoint_value}"
    return str(endpoint_type)


def _dom_id(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    return "-".join(part for part in cleaned.split("-") if part) or "item"


def _status_class(value: str) -> str:
    lowered = value.lower()
    if lowered in {"ready", "recorded", "allow", "cleared", "review_ready", "complete", "approved"}:
        return "ready"
    if lowered in {"blocked", "block", "failed"}:
        return "blocked"
    return "attention"


def _first_agent_id(state_data: JsonMap) -> str | None:
    agents = state_data.get("agents") if isinstance(state_data.get("agents"), dict) else {}
    passports = agents.get("passports") if isinstance(agents.get("passports"), list) else []
    for passport in passports:
        if isinstance(passport, dict) and isinstance(passport.get("id"), str) and passport["id"].strip():
            return passport["id"].strip()
    return None


def _query_value(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _json_script(value: JsonMap) -> str:
    return html.escape(json.dumps(value, sort_keys=True), quote=False)


def _escape(value: T.Any) -> str:
    return html.escape(str(value), quote=True)
