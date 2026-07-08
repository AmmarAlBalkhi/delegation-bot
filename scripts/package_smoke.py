#!/usr/bin/env python3
"""Smoke test the installed package from outside the source checkout."""

from __future__ import annotations

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
        "PASS: installed package control-loop demo, mission-status, agent-packet, app-state, workspace app-state, cockpit, approval-preview, app-export, app-serve, local workspace, agent-add, agent-run, Agent Passport, Agent Gate, approvals, RunPrint ingest, and Agent Gate audit smoke"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
