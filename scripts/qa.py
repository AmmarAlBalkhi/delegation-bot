#!/usr/bin/env python3
"""Run the local QA checks for DelegationHQ."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import typing as T
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    name: str
    command: list[str]


def run_check(check: Check) -> int:
    print(f"==> {check.name}", flush=True)
    result = subprocess.run(check.command, cwd=ROOT)
    if result.returncode == 0:
        print(f"PASS: {check.name}", flush=True)
    else:
        print(f"FAIL: {check.name} ({result.returncode})", flush=True)
    return result.returncode


def validate_schema_json() -> int:
    print("==> schema JSON parses", flush=True)
    schema_paths = sorted((ROOT / "schemas").glob("*.json"))
    try:
        for schema_path in schema_paths:
            with schema_path.open("r", encoding="utf-8") as handle:
                json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: schema JSON parses ({exc})", flush=True)
        return 1
    print(f"PASS: schema JSON parses ({len(schema_paths)} schema file(s))", flush=True)
    return 0


def validate_pyproject() -> int:
    print("==> package metadata parses", flush=True)
    try:
        import tomllib

        with (ROOT / "pyproject.toml").open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"FAIL: package metadata parses ({exc})", flush=True)
        return 1

    project = data.get("project")
    scripts = project.get("scripts") if isinstance(project, dict) else None
    if not isinstance(project, dict) or project.get("name") != "delegationhq":
        print("FAIL: package metadata parses (missing project name)", flush=True)
        return 1
    if project.get("license") != "Apache-2.0":
        print("FAIL: package metadata parses (license must match LICENSE)", flush=True)
        return 1
    license_files = project.get("license-files", [])
    if license_files != ["LICENSE", "NOTICE"]:
        print("FAIL: package metadata parses (license files must include LICENSE and NOTICE)", flush=True)
        return 1
    try:
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        notice_text = (ROOT / "NOTICE").read_text(encoding="utf-8")
    except OSError as exc:
        print(f"FAIL: package metadata parses ({exc})", flush=True)
        return 1
    if "Apache License" not in license_text or "Version 2.0" not in license_text:
        print("FAIL: package metadata parses (LICENSE must be Apache-2.0)", flush=True)
        return 1
    if "DelegationHQ" not in notice_text or "Ammar Al Balkhi" not in notice_text:
        print("FAIL: package metadata parses (NOTICE must identify the project)", flush=True)
        return 1
    classifiers = project.get("classifiers", [])
    if any(str(item).startswith("License ::") for item in classifiers if isinstance(item, str)):
        print("FAIL: package metadata parses (license classifiers conflict with SPDX license)", flush=True)
        return 1
    if not isinstance(scripts, dict) or scripts.get("delegation") != "delegation_bot.cli:main":
        print("FAIL: package metadata parses (missing delegation console command)", flush=True)
        return 1
    optional = project.get("optional-dependencies")
    exe_dependencies = optional.get("exe") if isinstance(optional, dict) else None
    if not isinstance(exe_dependencies, list) or not any("pyinstaller" in str(item).lower() for item in exe_dependencies):
        print("FAIL: package metadata parses (missing exe optional dependency group)", flush=True)
        return 1

    print("PASS: package metadata parses", flush=True)
    return 0


def playbook_paths() -> list[Path]:
    return sorted(path for path in (ROOT / "playbooks").glob("*.yaml") if path.name != "catalog.yaml")


def build_checks(python: str) -> list[Check]:
    checks = [
        Check(
            "bytecode compilation",
            [python, "-m", "compileall", "-q", "delegation_bot", "scripts", "tests"],
        ),
        Check(
            "unit tests",
            [python, "-m", "unittest", "discover", "-s", "tests", "-v"],
        ),
        Check(
            "example Harnessfile validates",
            [python, "scripts/delegation.py", "validate", "examples/ai-harness-control-plane.yaml"],
        ),
        Check(
            "CLI version",
            [python, "scripts/delegation.py", "--version"],
        ),
        Check(
            "doctor readiness",
            [python, "scripts/delegation.py", "doctor", "--skip-github"],
        ),
        Check(
            "release readiness",
            [python, "scripts/delegation.py", "release-check"],
        ),
        Check(
            "release rehearsal evidence bundle",
            [
                python,
                "scripts/delegation.py",
                "release-rehearse",
                "--output",
                ".delegation/qa-release-rehearsal",
            ],
        ),
        Check(
            "first-run demo",
            [python, "scripts/delegation.py", "demo", "--ledger", ".delegation/qa-demo.jsonl", "--control-loop"],
        ),
        Check(
            "mission status",
            [
                python,
                "scripts/delegation.py",
                "mission-status",
                "--ledger",
                ".delegation/qa-demo.jsonl",
            ],
        ),
        Check(
            "agent packet",
            [
                python,
                "scripts/delegation.py",
                "agent-packet",
                "--ledger",
                ".delegation/qa-demo.jsonl",
                "--action-id",
                "agent_gate.planner.write_issue_draft",
            ],
        ),
        Check(
            "local workspace init",
            [
                python,
                "scripts/delegation.py",
                "workspace-init",
                "--path",
                ".delegation/qa-local-workspace",
                "--name",
                "QA Local Workspace",
                "--owner",
                "Ammar",
                "--plan",
                "--force",
            ],
        ),
        Check(
            "local workspace status",
            [
                python,
                "scripts/delegation.py",
                "workspace-status",
                "--path",
                ".delegation/qa-local-workspace",
            ],
        ),
        Check(
            "custom agent add",
            [
                python,
                "scripts/delegation.py",
                "agent-add",
                "qa_cli_agent",
                "--registry",
                ".delegation/qa-local-workspace/.delegation/agents.yaml",
                "--command",
                f"{python} -c \"print('qa agent ok')\"",
                "--capability",
                "read.workspace",
                "--allowed-data",
                "workspace",
                "--evidence",
                "command_output",
                "--force",
            ],
        ),
        Check(
            "custom agent controlled run",
            [
                python,
                "scripts/delegation.py",
                "agent-run",
                "qa_cli_agent",
                "--registry",
                ".delegation/qa-local-workspace/.delegation/agents.yaml",
                "--ledger",
                ".delegation/qa-local-workspace/.delegation/agent-run.jsonl",
                "--action",
                "read.workspace",
                "--target",
                "workspace",
                "--execute",
                "--confirm",
                "LOCAL_AGENT_EXECUTION",
            ],
        ),
        Check(
            "EXE app plan",
            [python, "scripts/delegation.py", "app-plan"],
        ),
        Check(
            "EXE app state",
            [
                python,
                "scripts/delegation.py",
                "app-state",
                "--ledger",
                ".delegation/qa-demo.jsonl",
                "--harnessfile",
                "examples/ai-harness-control-plane.yaml",
            ],
        ),
        Check(
            "Agent Passport registry",
            [
                python,
                "scripts/delegation.py",
                "agents",
                "examples/ai-harness-control-plane.yaml",
                "--registry",
                "examples/agent-passports.yaml",
            ],
        ),
        Check(
            "Agent Gate receipt",
            [
                python,
                "scripts/delegation.py",
                "agent-gate",
                "examples/ai-harness-control-plane.yaml",
                "implementer",
                "--action",
                "create_pull_request",
                "--target",
                "repository",
                "--approval",
                "pull_request",
                "--ledger",
                ".delegation/qa-demo.jsonl",
                "--write",
            ],
        ),
        Check(
            "Agent Gate evidence audit",
            [
                python,
                "scripts/delegation.py",
                "agent-audit",
                "--ledger",
                ".delegation/qa-demo.jsonl",
            ],
        ),
        Check(
            "approval inbox",
            [
                python,
                "scripts/delegation.py",
                "approval-inbox",
                "--ledger",
                ".delegation/qa-demo.jsonl",
            ],
        ),
        Check(
            "approval decision receipt",
            [
                python,
                "scripts/delegation.py",
                "approval-decision",
                "--ledger",
                ".delegation/qa-demo.jsonl",
                "--action-id",
                "agent_gate.implementer.create_pull_request",
                "--decision",
                "approve",
                "--approver",
                "Ammar",
                "--reason",
                "QA smoke approval receipt.",
            ],
        ),
        Check(
            "RunPrint recording ingest",
            [
                python,
                "scripts/delegation.py",
                "runprint-ingest",
                "--ledger",
                ".delegation/qa-demo.jsonl",
                "--action-id",
                "agent_gate.implementer.create_pull_request",
                "--recording-id",
                "rec-qa-demo",
                "--bundle-id",
                "bundle-qa-demo",
                "--artifact",
                "run-ledger:jsonl:.delegation/qa-demo.jsonl",
                "--summary",
                "QA smoke recorded evidence.",
            ],
        ),
        Check(
            "Agent Gate recorded evidence audit",
            [
                python,
                "scripts/delegation.py",
                "agent-audit",
                "--ledger",
                ".delegation/qa-demo.jsonl",
            ],
        ),
        Check(
            "starter Harnessfile init",
            [
                python,
                "scripts/delegation.py",
                "init",
                "--goal",
                "prepare this repository for safe AI delegation",
                "--output",
                ".delegation/qa-init.yaml",
                "--force",
                "--plan",
                "--ledger",
                ".delegation/qa-init.jsonl",
            ],
        ),
        Check(
            "suggest release Harnessfile",
            [
                python,
                "scripts/delegation.py",
                "suggest",
                "prepare this repo for release",
                "--output",
                ".delegation/qa-suggested-release.yaml",
                "--plan",
                "--ledger",
                ".delegation/qa-suggested-release.jsonl",
            ],
        ),
        Check(
            "suggest OpenAI fixture Harnessfile",
            [
                python,
                "scripts/delegation.py",
                "suggest",
                "prepare this repo for release",
                "--draft-source",
                "fixture",
                "--provider",
                "openai",
                "--output",
                ".delegation/qa-model-openai-release.yaml",
                "--plan",
                "--ledger",
                ".delegation/qa-model-openai-release.jsonl",
            ],
        ),
        Check(
            "suggest Anthropic fixture Harnessfile",
            [
                python,
                "scripts/delegation.py",
                "suggest",
                "review this pull request",
                "--draft-source",
                "fixture",
                "--provider",
                "anthropic",
                "--output",
                ".delegation/qa-model-anthropic-review.yaml",
                "--plan",
                "--ledger",
                ".delegation/qa-model-anthropic-review.jsonl",
            ],
        ),
        Check(
            "package module CLI",
            [python, "-m", "delegation_bot", "adapters", "codex.thread"],
        ),
        Check(
            "installed package demo smoke",
            [python, "scripts/package_smoke.py"],
        ),
        Check(
            "example Harnessfile plans",
            [
                python,
                "scripts/delegation.py",
                "plan",
                "examples/ai-harness-control-plane.yaml",
                "--ledger",
                ".delegation/qa-latest.jsonl",
            ],
        ),
        Check(
            "adapter contracts list",
            [python, "scripts/delegation.py", "adapters"],
        ),
        Check(
            "adapter contract inspect",
            [python, "scripts/delegation.py", "adapters", "codex.thread", "--json"],
        ),
        Check(
            "sample adapter contract inspect",
            [python, "scripts/delegation.py", "adapters", "sample.echo", "--json"],
        ),
        Check(
            "example eval report",
            [
                python,
                "scripts/delegation.py",
                "eval",
                "examples/ai-harness-control-plane.yaml",
                "--ledger",
                ".delegation/qa-latest.jsonl",
                "--write",
            ],
        ),
        Check(
            "direct eval feedback drafts",
            [
                python,
                "scripts/delegation.py",
                "eval",
                "examples/ai-harness-control-plane.yaml",
                "--ledger",
                ".delegation/qa-latest.jsonl",
                "--feedback",
                "--feedback-include-blocked",
            ],
        ),
        Check(
            "example ledger report",
            [
                python,
                "scripts/delegation.py",
                "ledger",
                ".delegation/qa-latest.jsonl",
                "--adapter",
                "github.issue",
            ],
        ),
        Check(
            "example evidence bundle report",
            [
                python,
                "scripts/delegation.py",
                "evidence",
                "--ledger",
                ".delegation/qa-latest.jsonl",
            ],
        ),
        Check(
            "example OpenTelemetry export",
            [
                python,
                "scripts/delegation.py",
                "otel",
                ".delegation/qa-latest.jsonl",
                "--output",
                ".delegation/qa-latest-otel.json",
            ],
        ),
        Check(
            "github issue apply gate preview",
            [
                python,
                "scripts/delegation.py",
                "apply-issues",
                "examples/ai-harness-control-plane.yaml",
                "--ledger",
                ".delegation/qa-latest.jsonl",
            ],
        ),
        Check(
            "github actions dispatch gate preview",
            [
                python,
                "scripts/delegation.py",
                "apply-actions",
                "examples/ai-harness-control-plane.yaml",
                "--ledger",
                ".delegation/qa-latest.jsonl",
            ],
        ),
        Check(
            "github app scoped token plan",
            [
                python,
                "scripts/delegation.py",
                "github-app-plan",
                "--mode",
                "issue-write",
                "--repository",
                "AmmarAlBalkhi/delegation-bot",
                "--output",
                ".delegation/qa-github-app-plan.json",
            ],
        ),
        Check(
            "github actions cancel gate preview",
            [
                python,
                "scripts/delegation.py",
                "cancel-actions",
                "AmmarAlBalkhi/delegation-bot",
                "123",
            ],
        ),
        Check(
            "MCP tool policy gate",
            [
                python,
                "scripts/delegation.py",
                "mcp-gate",
                "examples/ai-harness-control-plane.yaml",
                "--ledger",
                ".delegation/qa-latest.jsonl",
            ],
        ),
        Check(
            "feedback issue drafts",
            [
                python,
                "scripts/delegation.py",
                "feedback",
                "examples/ai-harness-control-plane.yaml",
                "--ledger",
                ".delegation/qa-latest.jsonl",
                "--include-blocked",
                "--blocked-repeat-threshold",
                "1",
            ],
        ),
        Check(
            "example sample ledger report",
            [
                python,
                "scripts/delegation.py",
                "ledger",
                ".delegation/qa-latest.jsonl",
                "--adapter",
                "sample.echo",
            ],
        ),
        Check(
            "fixture good ledger report",
            [
                python,
                "scripts/delegation.py",
                "ledger",
                "examples/ledgers/adapter-good.jsonl",
                "--adapter",
                "sample.echo",
            ],
        ),
        Check(
            "fixture blocked ledger report",
            [
                python,
                "scripts/delegation.py",
                "ledger",
                "examples/ledgers/adapter-blocked.jsonl",
                "--status",
                "blocked",
            ],
        ),
        Check(
            "fixture failed ledger report",
            [
                python,
                "scripts/delegation.py",
                "ledger",
                "examples/ledgers/adapter-failed.jsonl",
                "--status",
                "failed",
            ],
        ),
        Check(
            "fixture applied github issue ledger report",
            [
                python,
                "scripts/delegation.py",
                "ledger",
                "examples/ledgers/github-issue-applied.jsonl",
                "--adapter",
                "github.issue",
            ],
        ),
        Check(
            "fixture github actions preview ledger report",
            [
                python,
                "scripts/delegation.py",
                "ledger",
                "examples/ledgers/github-actions-preview.jsonl",
                "--adapter",
                "github.actions",
            ],
        ),
        Check(
            "fixture MCP tool risk ledger report",
            [
                python,
                "scripts/delegation.py",
                "ledger",
                "examples/ledgers/mcp-tool-risk.jsonl",
                "--adapter",
                "mcp.tool",
            ],
        ),
        Check(
            "fixture feedback issue memory ledger report",
            [
                python,
                "scripts/delegation.py",
                "ledger",
                "examples/ledgers/feedback-issue-memory.jsonl",
                "--adapter",
                "github.issue",
            ],
        ),
        Check(
            "fixture feedback recovery ledger report",
            [
                python,
                "scripts/delegation.py",
                "ledger",
                "examples/ledgers/feedback-recovery.jsonl",
                "--adapter",
                "github.issue",
            ],
        ),
        Check(
            "dashboard snapshot fixture",
            [
                python,
                "scripts/delegation.py",
                "dashboard",
                "examples/ledgers/feedback-recovery.jsonl",
            ],
        ),
        Check(
            "adapter fixture generator",
            [
                python,
                "scripts/generate_adapter_fixtures.py",
                "mcp.tool",
                "--state",
                "good",
                "--output",
                ".delegation/qa-adapter-mcp-tool-good.jsonl",
            ],
        ),
        Check(
            "playbook catalog summary",
            [python, "scripts/delegation.py", "catalog"],
        ),
        Check(
            "playbook catalog filter",
            [python, "scripts/delegation.py", "catalog", "--tag", "release", "--adapter", "github.actions"],
        ),
        Check(
            "playbook catalog facets",
            [python, "scripts/delegation.py", "catalog", "--list-tags", "--list-adapters"],
        ),
        Check(
            "example promotion report",
            [
                python,
                "scripts/delegation.py",
                "promote",
                "examples/ai-harness-control-plane.yaml",
                "--ledger",
                ".delegation/qa-latest.jsonl",
            ],
        ),
    ]
    for path in playbook_paths():
        relative_path = str(path.relative_to(ROOT))
        checks.extend(
            [
                Check(
                    f"playbook validates: {path.stem}",
                    [python, "scripts/delegation.py", "validate", relative_path],
                ),
                Check(
                    f"playbook plans: {path.stem}",
                    [
                        python,
                        "scripts/delegation.py",
                        "plan",
                        relative_path,
                        "--ledger",
                        f".delegation/qa-{path.stem}.jsonl",
                    ],
                ),
            ]
        )
    return checks


def main(argv: T.Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use for subprocess checks.",
    )
    args = parser.parse_args(argv)

    failures = 0
    for check in build_checks(args.python):
        failures += 1 if run_check(check) else 0
    failures += 1 if validate_pyproject() else 0
    failures += 1 if validate_schema_json() else 0

    if failures:
        print(f"QA failed: {failures} check(s) failed", flush=True)
        return 1
    print("QA passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
