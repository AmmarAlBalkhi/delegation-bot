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

        registry = tmp / "agent-passports.yaml"
        registry.write_text(
            "\n".join(
                [
                    "version: delegation.agent-registry/v1",
                    "agents:",
                    "  - id: smoke_cli_agent",
                    "    runtime_type: cli.command",
                    "    command: delegation demo",
                    "    autonomy_level: suggest",
                    "    capabilities:",
                    "      - read.run_ledger",
                    "    allowed_data:",
                    "      - smoke",
                    "    evidence_requirements:",
                    "      - command_output",
                ]
            ),
            encoding="utf-8",
        )
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
                "smoke",
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
        "PASS: installed package control-loop demo, mission-status, agent-packet, app-state, Agent Passport, Agent Gate, approvals, RunPrint ingest, and Agent Gate audit smoke"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
