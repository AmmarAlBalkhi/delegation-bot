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
            ],
            cwd=tmp,
            env=env,
        )
        if agent_gate.returncode != 0 or "Agent Gate" not in agent_gate.stdout or "Decision: allow" not in agent_gate.stdout:
            print("FAIL: installed package Agent Gate smoke")
            print(agent_gate.stdout)
            print(agent_gate.stderr, file=sys.stderr)
            return agent_gate.returncode or 1

    print("PASS: installed package demo, app-state, Agent Passport, and Agent Gate smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
