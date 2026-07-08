#!/usr/bin/env python3
"""Local app shell export and server for DelegationHQ."""

from __future__ import annotations

import html
import json
import typing as T
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from delegation_bot.app_state import build_app_state
from delegation_bot.approval_preview import ApprovalPreviewReport, build_approval_preview_report


JsonMap = dict[str, T.Any]
DEFAULT_APP_DIR = ".delegation/cockpit"
DEFAULT_APP_HOST = "127.0.0.1"
DEFAULT_APP_PORT = 8765


@dataclass(frozen=True)
class LocalAppReport:
    status: str
    workspace: str
    output_dir: str | None
    index_html: str | None
    state_json: str | None
    approval_preview_json: str | None
    url: str | None
    preview_agent: str | None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> JsonMap:
        return {
            "status": self.status,
            "workspace": self.workspace,
            "output_dir": self.output_dir,
            "index_html": self.index_html,
            "state_json": self.state_json,
            "approval_preview_json": self.approval_preview_json,
            "url": self.url,
            "preview_agent": self.preview_agent,
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
        return tuple(actions)


def export_local_app(
    *,
    workspace_root: Path,
    output_dir: Path | None = None,
    preview_agent: str | None = None,
    preview_action: str = "read.workspace",
    preview_target: str = "workspace",
) -> LocalAppReport:
    """Write a static local cockpit bundle for a workspace."""

    workspace = workspace_root.resolve()
    target_dir = (output_dir or workspace / DEFAULT_APP_DIR).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    state = build_app_state(workspace_root=workspace)
    state_data = state.to_dict()
    preview = _build_default_preview(
        state_data,
        workspace_root=workspace,
        preview_agent=preview_agent,
        preview_action=preview_action,
        preview_target=preview_target,
    )
    preview_data = preview.to_dict() if preview else None

    state_path = target_dir / "state.json"
    preview_path = target_dir / "approval-preview.json"
    index_path = target_dir / "index.html"
    state_path.write_text(json.dumps(state_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if preview_data:
        preview_path.write_text(json.dumps(preview_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    index_path.write_text(_render_app_html(state_data, preview_data), encoding="utf-8")

    return LocalAppReport(
        status="ready",
        workspace=str(workspace),
        output_dir=str(target_dir),
        index_html=str(index_path),
        state_json=str(state_path),
        approval_preview_json=str(preview_path) if preview_data else None,
        url=index_path.as_uri(),
        preview_agent=preview.agent_id if preview else None,
    )


def serve_local_app(
    *,
    workspace_root: Path,
    host: str = DEFAULT_APP_HOST,
    port: int = DEFAULT_APP_PORT,
    preview_agent: str | None = None,
    preview_action: str = "read.workspace",
    preview_target: str = "workspace",
) -> None:
    """Serve the local cockpit until interrupted."""

    workspace = workspace_root.resolve()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API.
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                state_data = build_app_state(workspace_root=workspace).to_dict()
                preview = _preview_from_query(
                    parse_qs(parsed.query),
                    state_data=state_data,
                    workspace_root=workspace,
                    default_agent=preview_agent,
                    default_action=preview_action,
                    default_target=preview_target,
                )
                self._send_text(_render_app_html(state_data, preview.to_dict() if preview else None), "text/html")
                return
            if parsed.path == "/api/state":
                self._send_json(build_app_state(workspace_root=workspace).to_dict())
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
                )
                if preview is None:
                    self._send_json({"status": "empty", "message": "No agent passport is available."}, status=404)
                    return
                self._send_json(preview.to_dict())
                return
            if parsed.path == "/api/health":
                self._send_json({"status": "ready", "workspace": str(workspace)})
                return
            self._send_json({"status": "missing", "path": parsed.path}, status=404)

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

    server = ThreadingHTTPServer((host, port), Handler)
    server.serve_forever()


def app_server_report(*, workspace_root: Path, host: str = DEFAULT_APP_HOST, port: int = DEFAULT_APP_PORT) -> LocalAppReport:
    workspace = workspace_root.resolve()
    return LocalAppReport(
        status="ready",
        workspace=str(workspace),
        output_dir=None,
        index_html=None,
        state_json=None,
        approval_preview_json=None,
        url=f"http://{host}:{port}/",
        preview_agent=_first_agent_id(build_app_state(workspace_root=workspace).to_dict()),
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
    if report.state_json:
        lines.append(f"State JSON: {report.state_json}")
    if report.approval_preview_json:
        lines.append(f"Approval Preview JSON: {report.approval_preview_json}")
    if report.url:
        lines.append(f"URL: {report.url}")
    if report.preview_agent:
        lines.append(f"Preview agent: {report.preview_agent}")
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend(["", "Plain language:", "- This is a local app shell over the DelegationHQ control plane.", "- It reads workspace state and approval previews; live actions still use guarded commands."])
    lines.extend(["", "Next:"])
    lines.extend(f"- {action}" for action in report.next_actions)
    return "\n".join(lines)


def _build_default_preview(
    state_data: JsonMap,
    *,
    workspace_root: Path,
    preview_agent: str | None,
    preview_action: str,
    preview_target: str,
) -> ApprovalPreviewReport | None:
    agent_id = preview_agent or _first_agent_id(state_data)
    if not agent_id:
        return None
    return build_approval_preview_report(
        agent_id=agent_id,
        action=preview_action,
        target=preview_target,
        workspace_root=workspace_root,
    )


def _preview_from_query(
    query: dict[str, list[str]],
    *,
    state_data: JsonMap,
    workspace_root: Path,
    default_agent: str | None,
    default_action: str,
    default_target: str,
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
    )


def _render_app_html(state_data: JsonMap, preview_data: JsonMap | None) -> str:
    workspace = state_data.get("workspace") if isinstance(state_data.get("workspace"), dict) else {}
    ledger = state_data.get("ledger") if isinstance(state_data.get("ledger"), dict) else {}
    agents = state_data.get("agents") if isinstance(state_data.get("agents"), dict) else {}
    release = state_data.get("release") if isinstance(state_data.get("release"), dict) else {}
    next_actions = state_data.get("next_actions") if isinstance(state_data.get("next_actions"), list) else []
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
    <p class="subtle">Mission control for this workspace. Functional shell, not the final visual design.</p>
  </header>
  <main>
    <section class="grid" aria-label="Workspace status">
      {_metric_panel("Workspace", workspace.get("status", "unknown"), workspace.get("root", "No workspace loaded"))}
      {_metric_panel("Ledger", ledger.get("status", "unknown"), f"{ledger.get('event_count', 0)} events")}
      {_metric_panel("Agents", str(agents.get("passport_count", 0)), agents.get("status", "unknown"))}
      {_metric_panel("Release", release.get("status", "unknown"), f"{release.get('ready_count', 0)}/{release.get('ready_count', 0) + release.get('warning_count', 0) + release.get('failed_count', 0)} checks ready")}
    </section>
    <section class="panel">
      <h2>Approval Preview</h2>
      {_approval_preview_html(preview)}
    </section>
    <section class="grid">
      <div class="panel">
        <h2>Agent Passports</h2>
        {_agents_html(passports)}
      </div>
      <div class="panel">
        <h2>Next Actions</h2>
        {_list_html(next_actions[:6])}
      </div>
    </section>
    <section class="panel">
      <h2>Local Data</h2>
      <p class="subtle">This app shell is local-first. GitHub is an adapter, not the core.</p>
      <code>delegation app-state --workspace {_escape(workspace.get("root", "."))} --json</code>
    </section>
  </main>
  <script id="delegation-state" type="application/json">{_json_script(state_data)}</script>
  <script id="delegation-approval-preview" type="application/json">{_json_script(preview_data or {})}</script>
</body>
</html>
"""


def _metric_panel(title: str, value: T.Any, detail: T.Any) -> str:
    status_class = _status_class(str(value))
    return f"""<div class="panel">
  <h2>{_escape(title)}</h2>
  <span class="badge {status_class}">{_escape(value)}</span>
  <div class="metric">{_escape(detail)}</div>
</div>"""


def _approval_preview_html(preview: JsonMap) -> str:
    if not preview:
        return "<p class=\"subtle\">No agent passport is available yet.</p>"
    return f"""
<p><strong>{_escape(preview.get("summary", "No summary available."))}</strong></p>
<div class="grid">
  {_metric_panel("Decision", preview.get("decision", "unknown"), f"risk: {preview.get('risk', 'unknown')}")}
  {_metric_panel("Agent", preview.get("agent_id", "unknown"), preview.get("action", "unknown"))}
</div>
<p class="subtle">Required approvals</p>
{_list_html(preview.get("required_approvals") if isinstance(preview.get("required_approvals"), list) else [])}
<p class="subtle">Required evidence</p>
{_list_html(preview.get("required_evidence") if isinstance(preview.get("required_evidence"), list) else [])}
"""


def _agents_html(passports: list[T.Any]) -> str:
    if not passports:
        return "<p class=\"subtle\">No agents registered yet.</p>"
    items = []
    for item in passports[:8]:
        if not isinstance(item, dict):
            continue
        label = f"{item.get('id', 'unknown')} - {item.get('runtime_type', 'unknown')} - {item.get('autonomy_level', 'unknown')}"
        items.append(label)
    return _list_html(items)


def _list_html(values: T.Sequence[T.Any]) -> str:
    if not values:
        return "<p class=\"subtle\">none</p>"
    return "<ul>" + "".join(f"<li>{_escape(value)}</li>" for value in values) + "</ul>"


def _status_class(value: str) -> str:
    lowered = value.lower()
    if lowered in {"ready", "recorded", "allow"}:
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
