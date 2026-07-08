#!/usr/bin/env python3
"""Local-first workspace helpers for DelegationHQ."""

from __future__ import annotations

import typing as T
from dataclasses import dataclass
from pathlib import Path

from delegation_bot.agent_passports import build_agent_passport_report
from delegation_bot.harness_manifest import Manifest, load_manifest, validate_manifest
from delegation_bot.harness_plan import compile_plan, write_jsonl, build_dry_run_ledger


JsonMap = dict[str, T.Any]
DEFAULT_WORKSPACE_DIR = ".delegation"
DEFAULT_WORKSPACE_HARNESS = ".delegation/Harnessfile.yaml"
DEFAULT_WORKSPACE_REGISTRY = ".delegation/agents.yaml"
DEFAULT_WORKSPACE_LEDGER = ".delegation/local-workspace.jsonl"
DEFAULT_WORKSPACE_AGENT_RUN_LEDGER = ".delegation/agent-run.jsonl"
DEFAULT_WORKSPACE_AGENT_RUNS_DIR = ".delegation/agent-runs"


@dataclass(frozen=True)
class WorkspaceInitReport:
    status: str
    root: str
    harnessfile: str
    registry: str
    ledger: str | None
    workspace_name: str
    objective: str
    agent_count: int
    planned: bool
    action_count: int
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> JsonMap:
        return {
            "status": self.status,
            "root": self.root,
            "harnessfile": self.harnessfile,
            "registry": self.registry,
            "ledger": self.ledger,
            "workspace_name": self.workspace_name,
            "objective": self.objective,
            "agent_count": self.agent_count,
            "planned": self.planned,
            "action_count": self.action_count,
            "warnings": list(self.warnings),
            "next_actions": list(self.next_actions),
        }

    @property
    def next_actions(self) -> tuple[str, ...]:
        actions = [
            f"delegation workspace-status --path {self.root}",
            f"delegation agents --registry {self.registry}",
        ]
        if self.ledger:
            actions.extend(
                [
                    f"delegation mission-status --ledger {self.ledger}",
                    f"delegation ledger {self.ledger}",
                ]
            )
        else:
            actions.append(f"delegation plan {self.harnessfile} --ledger {DEFAULT_WORKSPACE_LEDGER}")
        actions.append(
            f"delegation agent-add local_cli_agent --registry {self.registry} --command \"python agent.py\" --capability read.workspace --allowed-data workspace --evidence command_output"
        )
        return tuple(actions)


@dataclass(frozen=True)
class WorkspaceStatusReport:
    status: str
    root: str
    harnessfile: str
    registry: str
    ledger: str
    harness_status: str
    registry_status: str
    ledger_status: str
    agent_count: int
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> JsonMap:
        return {
            "status": self.status,
            "root": self.root,
            "harnessfile": self.harnessfile,
            "registry": self.registry,
            "ledger": self.ledger,
            "harness_status": self.harness_status,
            "registry_status": self.registry_status,
            "ledger_status": self.ledger_status,
            "agent_count": self.agent_count,
            "warnings": list(self.warnings),
            "next_actions": list(self.next_actions),
        }

    @property
    def next_actions(self) -> tuple[str, ...]:
        if self.status == "missing":
            return (f"delegation workspace-init --path {self.root} --plan",)
        actions = [
            f"delegation plan {self.harnessfile} --ledger {self.ledger}",
            f"delegation agents --registry {self.registry}",
            f"delegation mission-status --ledger {self.ledger}",
        ]
        return tuple(actions)


def build_local_workspace_manifest(*, root: Path, name: str, owner: str, objective: str) -> Manifest:
    root_value = str(root)
    return {
        "version": "delegation.ai/v1",
        "id": _slug(name),
        "name": name,
        "objective": objective,
        "triggers": [{"type": "manual"}],
        "owners": {"accountable": owner, "reviewers": [owner]},
        "capability_packs": [
            {
                "id": "workspace_reader",
                "description": "Read local workspace files and run ledger evidence.",
                "capabilities": ["read.workspace", "read.run_ledger", "summarize.evidence"],
            },
            {
                "id": "workspace_drafter",
                "description": "Draft local plans and reports without external writes.",
                "capabilities": ["write.local_draft", "write.report_draft"],
                "approval_required_for": ["write.workspace"],
            },
            {
                "id": "local_risk_reviewer",
                "description": "Classify local mission risk before execution.",
                "capabilities": ["read.plan", "classify.risk", "suggest.policy"],
            },
        ],
        "agents": [
            {
                "id": "local_planner",
                "name": "Local Planner",
                "runtime": "cli.command",
                "autonomy_level": "suggest",
                "capability_packs": ["workspace_reader", "workspace_drafter", "local_risk_reviewer"],
            }
        ],
        "context": {
            "sources": [
                {"id": "workspace", "kind": "local_folder", "path": root_value, "trust": "high"},
                {"id": "operator_goal", "kind": "human", "trust": "medium"},
            ]
        },
        "executors": [
            {
                "id": "local_plan_note",
                "kind": "tool",
                "adapter": "sample.echo",
                "purpose": "Leave a no-network local planning receipt.",
                "inputs": {
                    "label": "local-workspace",
                    "message": f"Local DelegationHQ workspace initialized at {root_value}.",
                },
            },
            {
                "id": "local_risk_review",
                "kind": "ml_model",
                "adapter": "local.classifier",
                "purpose": "Classify local mission risk without a network call.",
                "inputs": {
                    "profile": "delegation.default",
                    "plan": objective,
                    "policy": "Local-first mode. Human approval is required before writes, external messages, or secret access.",
                },
            },
            {
                "id": "local_evidence_recorder",
                "kind": "recorder",
                "adapter": "runprint.recorder",
                "purpose": "Plan local RunPrint evidence capture for this workspace.",
                "inputs": {
                    "workspace": root_value,
                    "scope": "Record local ledger, approvals, changed files, command output, and eval reports.",
                    "artifacts": [
                        {"id": "run-ledger", "kind": "jsonl", "path": DEFAULT_WORKSPACE_LEDGER},
                        {"id": "workspace-report", "kind": "report", "path": ".delegation/workspace-status.json"},
                        {"id": "agent-registry", "kind": "yaml", "path": DEFAULT_WORKSPACE_REGISTRY},
                    ],
                },
            },
            {
                "id": "operator_approval",
                "kind": "human",
                "adapter": "human.approval",
                "purpose": "Keep local writes behind a human checkpoint.",
                "inputs": {
                    "approver": owner,
                    "request": "Approve moving from local dry-run planning to any workspace write.",
                },
            },
        ],
        "policies": {
            "approvals": {"required_for": ["write.workspace", "external_message", "secret_access"]},
            "budgets": {"max_usd_per_run": 0, "max_minutes_per_run": 15},
            "permissions": {
                "network": "restricted",
                "allowed_repositories": [],
                "allowed_mcp_servers": [],
                "allowed_mcp_tools": [],
            },
        },
        "outputs": [
            {"type": "sample.echo"},
            {"type": "risk_score"},
            {"type": "classification"},
            {"type": "evidence_bundle"},
            {"type": "approval"},
            {"type": "run_ledger"},
            {"type": "eval_report"},
        ],
        "evals": [
            {
                "id": "ledger_is_valid",
                "type": "invariant",
                "description": "The local workspace ledger must stay readable and ordered.",
            },
            {
                "id": "approvals_before_risky_actions",
                "type": "policy",
                "description": "Local writes, external messages, and secret access require approval evidence.",
            },
            {
                "id": "required_adapter_evidence",
                "type": "invariant",
                "description": "Local adapters must leave required evidence before trust increases.",
            },
        ],
        "metadata": {
            "local_first": True,
            "github_required": False,
            "workspace_root": root_value,
            "product_loop": "plan -> gate -> approve -> record -> ledger -> eval -> promote",
        },
    }


def build_default_agent_registry(*, root: Path) -> JsonMap:
    return {
        "version": "delegation.agent-registry/v1",
        "agents": [
            {
                "id": "local_cli_agent",
                "name": "Local CLI Agent",
                "runtime_type": "cli.command",
                "command": "python agent.py",
                "autonomy_level": "suggest",
                "risk_level": "low",
                "capabilities": ["read.workspace", "read.run_ledger", "summarize.evidence"],
                "allowed_tools": ["local.read_files", "local.command_output"],
                "allowed_data": ["workspace", "run_ledger"],
                "required_approvals": [],
                "expected_outputs": ["summary", "command_output", "run_ledger"],
                "evidence_requirements": ["run_ledger", "command_output"],
                "promotion_evals": ["ledger_is_valid"],
            }
        ],
        "metadata": {"workspace_root": str(root), "github_required": False},
    }


def initialize_local_workspace(
    *,
    root: Path,
    name: str,
    owner: str,
    objective: str,
    force: bool = False,
    plan: bool = False,
    ledger_path: Path | None = None,
) -> WorkspaceInitReport:
    resolved_root = root.resolve()
    workspace_dir = resolved_root / DEFAULT_WORKSPACE_DIR
    harness_path = resolved_root / DEFAULT_WORKSPACE_HARNESS
    registry_path = resolved_root / DEFAULT_WORKSPACE_REGISTRY
    target_ledger = (resolved_root / DEFAULT_WORKSPACE_LEDGER) if ledger_path is None else _resolve_child(resolved_root, ledger_path)

    if not force:
        existing = [path for path in (harness_path, registry_path) if path.exists()]
        if existing:
            raise FileExistsError("Workspace files already exist: " + ", ".join(str(path) for path in existing))

    manifest = build_local_workspace_manifest(root=resolved_root, name=name, owner=owner, objective=objective)
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("; ".join(errors))

    workspace_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml(harness_path, manifest)
    _write_yaml(registry_path, build_default_agent_registry(root=resolved_root))

    action_count = 0
    ledger_value = None
    if plan:
        compiled = compile_plan(manifest, source=str(harness_path))
        write_jsonl(build_dry_run_ledger(compiled), target_ledger)
        action_count = len(compiled.actions)
        ledger_value = str(target_ledger)

    return WorkspaceInitReport(
        status="ready",
        root=str(resolved_root),
        harnessfile=str(harness_path),
        registry=str(registry_path),
        ledger=ledger_value,
        workspace_name=name,
        objective=objective,
        agent_count=1,
        planned=plan,
        action_count=action_count,
    )


def build_workspace_status(*, root: Path, ledger_path: Path | None = None) -> WorkspaceStatusReport:
    resolved_root = root.resolve()
    harness_path = resolved_root / DEFAULT_WORKSPACE_HARNESS
    registry_path = resolved_root / DEFAULT_WORKSPACE_REGISTRY
    target_ledger = (resolved_root / DEFAULT_WORKSPACE_LEDGER) if ledger_path is None else _resolve_child(resolved_root, ledger_path)
    warnings: list[str] = []

    harness_status = "missing"
    if harness_path.exists():
        try:
            manifest = load_manifest(harness_path)
            errors = validate_manifest(manifest)
            if errors:
                harness_status = "invalid"
                warnings.extend(f"Harnessfile: {error}" for error in errors)
            else:
                harness_status = "ready"
        except Exception as exc:  # noqa: BLE001 - report status instead of crashing user-facing command.
            harness_status = "error"
            warnings.append(f"Harnessfile could not be read: {exc}")

    registry_report = build_agent_passport_report(registry_paths=(registry_path,)) if registry_path.exists() else None
    registry_status = registry_report.status if registry_report else "missing"
    if registry_report:
        warnings.extend(registry_report.warnings)
    ledger_status = "ready" if target_ledger.exists() else "missing"
    status = _workspace_status(harness_status, registry_status, ledger_status)
    return WorkspaceStatusReport(
        status=status,
        root=str(resolved_root),
        harnessfile=str(harness_path),
        registry=str(registry_path),
        ledger=str(target_ledger),
        harness_status=harness_status,
        registry_status=registry_status,
        ledger_status=ledger_status,
        agent_count=registry_report.passport_count if registry_report else 0,
        warnings=tuple(warnings),
    )


def render_workspace_init_report(report: WorkspaceInitReport) -> str:
    lines = [
        "Local Workspace Created",
        "",
        f"Status: {report.status}",
        f"Root: {report.root}",
        f"Harnessfile: {report.harnessfile}",
        f"Agent registry: {report.registry}",
        "GitHub required: false",
        f"Agents: {report.agent_count}",
    ]
    if report.planned and report.ledger:
        lines.extend([f"Dry-run actions: {report.action_count}", f"Ledger: {report.ledger}"])
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend(["", "Plain language:", "- This folder is now an AI workspace.", "- DelegationHQ can plan, gate, approve, record, and evaluate without GitHub."])
    lines.extend(["", "Next:"])
    lines.extend(f"- {action}" for action in report.next_actions)
    return "\n".join(lines)


def render_workspace_status(report: WorkspaceStatusReport) -> str:
    lines = [
        "Local Workspace Status",
        "",
        f"Status: {report.status}",
        f"Root: {report.root}",
        f"Harnessfile: {report.harness_status} ({report.harnessfile})",
        f"Agent registry: {report.registry_status} ({report.registry})",
        f"Ledger: {report.ledger_status} ({report.ledger})",
        f"Agents: {report.agent_count}",
        "GitHub required: false",
    ]
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend(["", "Next:"])
    lines.extend(f"- {action}" for action in report.next_actions)
    return "\n".join(lines)


def _workspace_status(harness_status: str, registry_status: str, ledger_status: str) -> str:
    if harness_status == "missing" and registry_status == "missing":
        return "missing"
    if harness_status in {"error", "invalid"} or registry_status == "warning":
        return "needs_attention"
    if harness_status == "ready" and registry_status == "ready" and ledger_status == "ready":
        return "ready"
    return "usable"


def _resolve_child(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _write_yaml(path: Path, data: JsonMap) -> None:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to write workspace YAML files") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=False), encoding="utf-8")


def _slug(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    return "-".join(part for part in cleaned.split("-") if part) or "local-workspace"
