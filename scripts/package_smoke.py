#!/usr/bin/env python3
"""Smoke test the installed package from outside the source checkout."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="delegation-package-smoke-") as tmpdir:
        tmp = Path(tmpdir)
        site_dir = tmp / "site"
        install = _run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--quiet",
                "--no-deps",
                "--target",
                str(site_dir),
                str(ROOT),
            ],
            cwd=tmp,
        )
        if install.returncode != 0:
            print("FAIL: package install smoke")
            print(install.stdout)
            print(install.stderr, file=sys.stderr)
            return install.returncode

        env = dict(os.environ)
        env["PYTHONPATH"] = str(site_dir)
        version = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "--version",
            ],
            cwd=tmp,
            env=env,
        )
        if version.returncode != 0 or "DelegationHQ " not in version.stdout:
            print("FAIL: installed package version smoke")
            print(version.stdout)
            print(version.stderr, file=sys.stderr)
            return version.returncode or 1

        ledger = tmp / "demo.jsonl"
        demo = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "demo",
                "--ledger",
                str(ledger),
                "--control-loop",
            ],
            cwd=tmp,
            env=env,
        )
        if demo.returncode != 0:
            print("FAIL: installed package demo smoke")
            print(demo.stdout)
            print(demo.stderr, file=sys.stderr)
            return demo.returncode
        if "Status: ready" not in demo.stdout or not ledger.exists():
            print("FAIL: installed package demo smoke did not produce ready output and ledger")
            print(demo.stdout)
            return 1

        mission_status = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "mission-status",
                "--ledger",
                str(ledger),
            ],
            cwd=tmp,
            env=env,
        )
        if mission_status.returncode != 0 or "DelegationHQ Mission Status" not in mission_status.stdout:
            print("FAIL: installed package mission-status smoke")
            print(mission_status.stdout)
            print(mission_status.stderr, file=sys.stderr)
            return mission_status.returncode or 1

        agent_packet = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "agent-packet",
                "--ledger",
                str(ledger),
                "--action-id",
                "agent_gate.planner.write_issue_draft",
            ],
            cwd=tmp,
            env=env,
        )
        if agent_packet.returncode != 0 or "Agent Packet" not in agent_packet.stdout:
            print("FAIL: installed package agent-packet smoke")
            print(agent_packet.stdout)
            print(agent_packet.stderr, file=sys.stderr)
            return agent_packet.returncode or 1

        app_state = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "app-state",
                "--ledger",
                str(ledger),
            ],
            cwd=tmp,
            env=env,
        )
        if app_state.returncode != 0 or "DelegationHQ App State" not in app_state.stdout:
            print("FAIL: installed package app-state smoke")
            print(app_state.stdout)
            print(app_state.stderr, file=sys.stderr)
            return app_state.returncode or 1

        workspace = tmp / "workspace"
        workspace_init = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "workspace-init",
                "--path",
                str(workspace),
                "--owner",
                "package-smoke",
                "--plan",
            ],
            cwd=tmp,
            env=env,
        )
        if workspace_init.returncode != 0 or "Local Workspace Created" not in workspace_init.stdout:
            print("FAIL: installed package workspace-init smoke")
            print(workspace_init.stdout)
            print(workspace_init.stderr, file=sys.stderr)
            return workspace_init.returncode or 1

        workspace_status = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "workspace-status",
                "--path",
                str(workspace),
            ],
            cwd=tmp,
            env=env,
        )
        if workspace_status.returncode != 0 or "Local Workspace Status" not in workspace_status.stdout:
            print("FAIL: installed package workspace-status smoke")
            print(workspace_status.stdout)
            print(workspace_status.stderr, file=sys.stderr)
            return workspace_status.returncode or 1

        registry = workspace / ".delegation" / "agents.yaml"
        agent_add = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "agent-add",
                "smoke_cli_agent",
                "--workspace",
                str(workspace),
                "--command",
                f"{sys.executable} -c \"print('package agent ok')\"",
                "--capability",
                "read.workspace",
                "--capability",
                "read.run_ledger",
                "--allowed-data",
                "workspace",
                "--allowed-data",
                "run_ledger",
                "--evidence",
                "command_output",
                "--force",
            ],
            cwd=tmp,
            env=env,
        )
        if agent_add.returncode != 0 or "Agent Added" not in agent_add.stdout:
            print("FAIL: installed package agent-add smoke")
            print(agent_add.stdout)
            print(agent_add.stderr, file=sys.stderr)
            return agent_add.returncode or 1

        agent_run = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "agent-run",
                "smoke_cli_agent",
                "--workspace",
                str(workspace),
                "--execute",
                "--confirm",
                "LOCAL_AGENT_EXECUTION",
            ],
            cwd=tmp,
            env=env,
        )
        if agent_run.returncode != 0 or "Agent Run" not in agent_run.stdout or "package agent ok" not in agent_run.stdout:
            print("FAIL: installed package agent-run smoke")
            print(agent_run.stdout)
            print(agent_run.stderr, file=sys.stderr)
            return agent_run.returncode or 1

        workspace_app_state = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "app-state",
                "--workspace",
                str(workspace),
            ],
            cwd=tmp,
            env=env,
        )
        if (
            workspace_app_state.returncode != 0
            or "DelegationHQ App State" not in workspace_app_state.stdout
            or "Workspace:" not in workspace_app_state.stdout
        ):
            print("FAIL: installed package workspace app-state smoke")
            print(workspace_app_state.stdout)
            print(workspace_app_state.stderr, file=sys.stderr)
            return workspace_app_state.returncode or 1

        cockpit = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "cockpit",
                "--workspace",
                str(workspace),
            ],
            cwd=tmp,
            env=env,
        )
        if cockpit.returncode != 0 or "Workspace:" not in cockpit.stdout:
            print("FAIL: installed package cockpit smoke")
            print(cockpit.stdout)
            print(cockpit.stderr, file=sys.stderr)
            return cockpit.returncode or 1

        workspace_flow = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "workspace-flow",
                "--workspace",
                str(workspace),
            ],
            cwd=tmp,
            env=env,
        )
        if workspace_flow.returncode != 0 or "DelegationHQ Workspace Flow" not in workspace_flow.stdout:
            print("FAIL: installed package workspace-flow smoke")
            print(workspace_flow.stdout)
            print(workspace_flow.stderr, file=sys.stderr)
            return workspace_flow.returncode or 1

        demo_workspace = tmp / "demo-workspace"
        workspace_demo = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "workspace-demo",
                "--path",
                str(demo_workspace),
                "--force",
                "--approve",
                "--execute",
                "--confirm",
                "LOCAL_AGENT_EXECUTION",
                "--export-app",
            ],
            cwd=tmp,
            env=env,
        )
        if (
            workspace_demo.returncode != 0
            or "DelegationHQ Workspace Demo" not in workspace_demo.stdout
            or "Executed: true" not in workspace_demo.stdout
        ):
            print("FAIL: installed package workspace-demo smoke")
            print(workspace_demo.stdout)
            print(workspace_demo.stderr, file=sys.stderr)
            return workspace_demo.returncode or 1

        app_dashboard = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "app-dashboard",
                "--workspace",
                str(workspace),
                "--preview-agent",
                "smoke_cli_agent",
            ],
            cwd=tmp,
            env=env,
        )
        if app_dashboard.returncode != 0 or "DelegationHQ App Dashboard" not in app_dashboard.stdout:
            print("FAIL: installed package app-dashboard smoke")
            print(app_dashboard.stdout)
            print(app_dashboard.stderr, file=sys.stderr)
            return app_dashboard.returncode or 1

        timeline = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "timeline",
                "--workspace",
                str(workspace),
            ],
            cwd=tmp,
            env=env,
        )
        if timeline.returncode != 0 or "DelegationHQ Mission Timeline" not in timeline.stdout:
            print("FAIL: installed package timeline smoke")
            print(timeline.stdout)
            print(timeline.stderr, file=sys.stderr)
            return timeline.returncode or 1

        approval_preview = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "approval-preview",
                "smoke_cli_agent",
                "--workspace",
                str(workspace),
            ],
            cwd=tmp,
            env=env,
        )
        if approval_preview.returncode != 0 or "Agent Approval Preview" not in approval_preview.stdout:
            print("FAIL: installed package approval-preview smoke")
            print(approval_preview.stdout)
            print(approval_preview.stderr, file=sys.stderr)
            return approval_preview.returncode or 1

        app_export = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "app-export",
                "--workspace",
                str(workspace),
                "--output",
                str(workspace / ".delegation" / "cockpit"),
                "--preview-agent",
                "smoke_cli_agent",
            ],
            cwd=tmp,
            env=env,
        )
        if app_export.returncode != 0 or "DelegationHQ Local App" not in app_export.stdout:
            print("FAIL: installed package app-export smoke")
            print(app_export.stdout)
            print(app_export.stderr, file=sys.stderr)
            return app_export.returncode or 1
        if not (workspace / ".delegation" / "cockpit" / "index.html").exists():
            print("FAIL: installed package app-export index.html missing")
            return 1
        app_index_text = (workspace / ".delegation" / "cockpit" / "index.html").read_text(encoding="utf-8")
        if "Add Agent Passport" not in app_index_text or "Mission Result" not in app_index_text:
            print("FAIL: installed package app-export missing functional app sections")
            return 1

        app_serve = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "app-serve",
                "--workspace",
                str(workspace),
                "--dry-run",
            ],
            cwd=tmp,
            env=env,
        )
        if app_serve.returncode != 0 or "http://127.0.0.1:8765/" not in app_serve.stdout:
            print("FAIL: installed package app-serve dry-run smoke")
            print(app_serve.stdout)
            print(app_serve.stderr, file=sys.stderr)
            return app_serve.returncode or 1
        app_serve_actions = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "app-serve",
                "--workspace",
                str(workspace),
                "--dry-run",
                "--allow-actions",
                "--json",
            ],
            cwd=tmp,
            env=env,
        )
        if (
            app_serve_actions.returncode != 0
            or '"actions_enabled": true' not in app_serve_actions.stdout
            or "http://127.0.0.1:8765/" not in app_serve_actions.stdout
        ):
            print("FAIL: installed package guarded app actions smoke")
            print(app_serve_actions.stdout)
            print(app_serve_actions.stderr, file=sys.stderr)
            return app_serve_actions.returncode or 1

        agents = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "agents",
                "--registry",
                str(registry),
            ],
            cwd=tmp,
            env=env,
        )
        if agents.returncode != 0 or "Agent Passport Registry" not in agents.stdout:
            print("FAIL: installed package Agent Passport smoke")
            print(agents.stdout)
            print(agents.stderr, file=sys.stderr)
            return agents.returncode or 1

        agent_gate = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "agent-gate",
                "--registry",
                str(registry),
                "smoke_cli_agent",
                "--action",
                "read.run_ledger",
                "--target",
                "run_ledger",
                "--ledger",
                str(ledger),
                "--write",
            ],
            cwd=tmp,
            env=env,
        )
        if agent_gate.returncode != 0 or "Agent Gate" not in agent_gate.stdout or "Decision: allow" not in agent_gate.stdout:
            print("FAIL: installed package Agent Gate smoke")
            print(agent_gate.stdout)
            print(agent_gate.stderr, file=sys.stderr)
            return agent_gate.returncode or 1

        action_request = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "action-request",
                "smoke_cli_agent",
                "--workspace",
                str(workspace),
                "--action",
                "read.run_ledger",
                "--target",
                "run_ledger",
                "--summary",
                "Smoke agent requests read access through the cockpit.",
            ],
            cwd=tmp,
            env=env,
        )
        if action_request.returncode != 0 or "Action Request" not in action_request.stdout:
            print("FAIL: installed package action-request smoke")
            print(action_request.stdout)
            print(action_request.stderr, file=sys.stderr)
            return action_request.returncode or 1

        active_request_dashboard = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "app-dashboard",
                "--workspace",
                str(workspace),
                "--json",
            ],
            cwd=tmp,
            env=env,
        )
        if (
            active_request_dashboard.returncode != 0
            or '"active_request"' not in active_request_dashboard.stdout
            or '"result_summary"' not in active_request_dashboard.stdout
            or "Smoke agent requests read access through the cockpit." not in active_request_dashboard.stdout
        ):
            print("FAIL: installed package active request dashboard smoke")
            print(active_request_dashboard.stdout)
            print(active_request_dashboard.stderr, file=sys.stderr)
            return active_request_dashboard.returncode or 1

        approval_inbox = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "approval-inbox",
                "--ledger",
                str(ledger),
            ],
            cwd=tmp,
            env=env,
        )
        if approval_inbox.returncode != 0 or "Approval Inbox" not in approval_inbox.stdout:
            print("FAIL: installed package approval inbox smoke")
            print(approval_inbox.stdout)
            print(approval_inbox.stderr, file=sys.stderr)
            return approval_inbox.returncode or 1

        approval_decision = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "approval-decision",
                "--ledger",
                str(ledger),
                "--action-id",
                "agent_gate.smoke_cli_agent.read_run_ledger",
                "--decision",
                "approve",
                "--approver",
                "package-smoke",
            ],
            cwd=tmp,
            env=env,
        )
        if approval_decision.returncode != 0 or "Approval Decision" not in approval_decision.stdout:
            print("FAIL: installed package approval decision smoke")
            print(approval_decision.stdout)
            print(approval_decision.stderr, file=sys.stderr)
            return approval_decision.returncode or 1

        request_status = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "request-status",
                "--workspace",
                str(workspace),
                "--action-id",
                "agent_gate.smoke_cli_agent.read_run_ledger",
            ],
            cwd=tmp,
            env=env,
        )
        if request_status.returncode != 0 or "Request Status" not in request_status.stdout:
            print("FAIL: installed package request-status smoke")
            print(request_status.stdout)
            print(request_status.stderr, file=sys.stderr)
            return request_status.returncode or 1

        request_run = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "request-run",
                "--workspace",
                str(workspace),
                "--action-id",
                "agent_gate.smoke_cli_agent.read_run_ledger",
                "--confirm",
                "LOCAL_AGENT_EXECUTION",
            ],
            cwd=tmp,
            env=env,
        )
        if request_run.returncode != 0 or "Request Run" not in request_run.stdout or "package agent ok" not in request_run.stdout:
            print("FAIL: installed package request-run smoke")
            print(request_run.stdout)
            print(request_run.stderr, file=sys.stderr)
            return request_run.returncode or 1

        agent_result_path = tmp / "agent-result.json"
        agent_result_path.write_text(
            json.dumps(
                {
                    "schema_version": "delegation.agent-result.v1",
                    "action_id": "agent_gate.smoke_cli_agent.read_run_ledger",
                    "agent_id": "smoke_cli_agent",
                    "status": "completed",
                    "summary": "Installed package worker returned controlled result evidence.",
                    "changed_resources": ["run_ledger"],
                    "runprint_recording_id": "rec-agent-result-package-smoke",
                    "evidence_bundle_id": "bundle-agent-result-package-smoke",
                    "artifacts": [
                        {
                            "id": "run-ledger",
                            "kind": "jsonl",
                            "path": "demo.jsonl",
                        }
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        agent_result_ingest = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "agent-result-ingest",
                "--ledger",
                str(ledger),
                "--action-id",
                "agent_gate.smoke_cli_agent.read_run_ledger",
                "--result",
                str(agent_result_path),
            ],
            cwd=tmp,
            env=env,
        )
        if agent_result_ingest.returncode != 0 or "Agent Result Ingest" not in agent_result_ingest.stdout:
            print("FAIL: installed package agent result ingest smoke")
            print(agent_result_ingest.stdout)
            print(agent_result_ingest.stderr, file=sys.stderr)
            return agent_result_ingest.returncode or 1

        evidence_ingest = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "evidence-ingest",
                "--ledger",
                str(ledger),
                "--tool",
                "test-reporter",
                "--tool-kind",
                "test",
                "--action-id",
                "agent_gate.smoke_cli_agent.read_run_ledger",
                "--recording-id",
                "rec-evidence-package-smoke",
                "--bundle-id",
                "bundle-evidence-package-smoke",
                "--artifact",
                "test-report:junit:package-smoke-tests.xml",
                "--summary",
                "Installed package smoke recorded generic evidence.",
            ],
            cwd=tmp,
            env=env,
        )
        if evidence_ingest.returncode != 0 or "Evidence Recording Ingest" not in evidence_ingest.stdout:
            print("FAIL: installed package generic evidence ingest smoke")
            print(evidence_ingest.stdout)
            print(evidence_ingest.stderr, file=sys.stderr)
            return evidence_ingest.returncode or 1

        runprint_ingest = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "runprint-ingest",
                "--ledger",
                str(ledger),
                "--action-id",
                "agent_gate.smoke_cli_agent.read_run_ledger",
                "--recording-id",
                "rec-package-smoke",
                "--bundle-id",
                "bundle-package-smoke",
                "--artifact",
                "run-ledger:jsonl:demo.jsonl",
                "--summary",
                "Installed package smoke recorded evidence.",
            ],
            cwd=tmp,
            env=env,
        )
        if runprint_ingest.returncode != 0 or "RunPrint Recording Ingest" not in runprint_ingest.stdout:
            print("FAIL: installed package RunPrint ingest smoke")
            print(runprint_ingest.stdout)
            print(runprint_ingest.stderr, file=sys.stderr)
            return runprint_ingest.returncode or 1

        agent_audit = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "agent-audit",
                "--ledger",
                str(ledger),
            ],
            cwd=tmp,
            env=env,
        )
        if (
            agent_audit.returncode != 0
            or "Agent Gate Evidence Audit" not in agent_audit.stdout
            or "Status: recorded" not in agent_audit.stdout
        ):
            print("FAIL: installed package Agent Gate audit smoke")
            print(agent_audit.stdout)
            print(agent_audit.stderr, file=sys.stderr)
            return agent_audit.returncode or 1

        print(
            "PASS: installed package control-loop demo, mission-status, timeline, agent-packet, agent-result-ingest, generic evidence ingest, app-state, workspace app-state, cockpit, workspace-flow, workspace-demo, app-dashboard, active request dashboard, result summary, approval-preview, app-export functional sections, app-serve, guarded app actions, local workspace, agent-add, agent-run, action-request, request-status, request-run, Agent Passport, Agent Gate, approvals, RunPrint ingest, and Agent Gate audit smoke"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
