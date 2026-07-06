"""First-run demo and starter Harnessfile helpers."""

from __future__ import annotations

import re
import shutil
import subprocess
import typing as T
from dataclasses import dataclass
from pathlib import Path

from delegation_bot.evals import EvalResult, run_declared_evals
from delegation_bot.github_actions_apply import GitHubActionsApplyReport, build_actions_apply_report
from delegation_bot.harness_manifest import Manifest, load_manifest, validate_manifest
from delegation_bot.harness_plan import ExecutionPlan, build_dry_run_ledger, compile_plan, write_jsonl
from delegation_bot.ledger import LedgerFilter, build_ledger_view
from delegation_bot.mcp_policy_gate import McpPolicyReport, build_mcp_policy_report
from delegation_bot.suggest import DEFAULT_REPOSITORY, build_suggestion, manifest_to_yaml


JsonMap = dict[str, T.Any]
DEFAULT_DEMO_LEDGER = ".delegation/demo.jsonl"
DEFAULT_INIT_GOAL = "prepare this repository for safe AI delegation"
DEFAULT_INIT_OUTPUT = "Harnessfile.yaml"


@dataclass(frozen=True)
class FirstRunStep:
    name: str
    status: str
    message: str

    def to_dict(self) -> JsonMap:
        return {"name": self.name, "status": self.status, "message": self.message}


@dataclass(frozen=True)
class DemoReport:
    status: str
    harness_source: str
    ledger_path: str
    plan: ExecutionPlan
    ledger_event_count: int
    mcp_report: McpPolicyReport
    actions_report: GitHubActionsApplyReport
    eval_results: tuple[EvalResult, ...]
    steps: tuple[FirstRunStep, ...]

    @property
    def blocked(self) -> bool:
        return self.status != "ready"

    def to_dict(self) -> JsonMap:
        return {
            "status": self.status,
            "harness_source": self.harness_source,
            "ledger_path": self.ledger_path,
            "plan": self.plan.to_dict(),
            "ledger_event_count": self.ledger_event_count,
            "mcp_gate": self.mcp_report.to_dict(),
            "github_actions_gate": self.actions_report.to_dict(),
            "evals": [result.to_dict() for result in self.eval_results],
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(frozen=True)
class InitReport:
    status: str
    output_path: str
    repository: str
    owner: str
    template_id: str
    harness_id: str
    planned: bool = False
    ledger_path: str | None = None
    action_count: int = 0

    def to_dict(self) -> JsonMap:
        return {
            "status": self.status,
            "output_path": self.output_path,
            "repository": self.repository,
            "owner": self.owner,
            "template_id": self.template_id,
            "harness_id": self.harness_id,
            "planned": self.planned,
            "ledger_path": self.ledger_path,
            "action_count": self.action_count,
        }


def build_demo_manifest(*, repository: str = DEFAULT_REPOSITORY, owner: str = "maintainer") -> Manifest:
    """Return a small built-in Harnessfile that works outside the source checkout."""

    return {
        "version": "delegation.ai/v1",
        "id": "demo-ai-mission-control",
        "name": "Demo: AI Mission Control",
        "objective": "Show a safe agentic mission with model planning, MCP tool policy, GitHub workflow preview, ledger evidence, and evals.",
        "triggers": [{"type": "manual"}],
        "owners": {"accountable": owner, "reviewers": [owner]},
        "models": [
            {
                "id": "planner_model",
                "provider": "openai",
                "model": "gpt-5.5",
                "role": "planning",
                "budget_usd": 1,
            },
            {
                "id": "local_policy_model",
                "provider": "local",
                "adapter": "ollama",
                "model": "llama-guard",
                "role": "policy_review",
            },
        ],
        "capability_packs": [
            {
                "id": "repo_reader",
                "description": "Read repository files, plans, and run ledger evidence.",
                "capabilities": ["read.repository", "read.run_ledger"],
            },
            {
                "id": "mission_drafter",
                "description": "Draft plans and issue text without publishing.",
                "capabilities": ["write.plan_draft", "write.issue_draft"],
                "approval_required_for": ["publish.issue"],
            },
            {
                "id": "policy_reviewer",
                "description": "Classify tool and workflow risk before execution.",
                "capabilities": ["read.plan", "classify.risk", "suggest.policy"],
            },
        ],
        "agents": [
            {
                "id": "planner",
                "runtime": "openai.agents",
                "model": "planner_model",
                "autonomy_level": "draft",
                "capability_packs": ["repo_reader", "mission_drafter", "policy_reviewer"],
            },
            {
                "id": "policy_guard",
                "runtime": "local.classifier",
                "model": "local_policy_model",
                "autonomy_level": "suggest",
                "capability_packs": ["policy_reviewer"],
            },
        ],
        "context": {
            "sources": [
                {"id": "repository", "kind": "git", "trust": "high"},
                {"id": "operator_goal", "kind": "human", "trust": "medium"},
            ]
        },
        "executors": [
            {
                "id": "mission_issue",
                "kind": "workflow",
                "adapter": "github.issue",
                "purpose": "Preview the tracking issue that would hold the approved mission plan.",
                "inputs": {
                    "repository": repository,
                    "issue_title": "DelegationHQ demo: approved AI mission",
                    "issue_body": "Track the dry-run plan, policy gates, ledger evidence, and evals before live execution.",
                },
            },
            {
                "id": "planner_agent",
                "kind": "ai_harness",
                "adapter": "openai.agents",
                "model": "planner_model",
                "purpose": "Plan the mission through an OpenAI Agents SDK-style workflow.",
                "inputs": {
                    "model": "gpt-5.5",
                    "instructions": "Draft a safe mission with explicit evidence and approval gates.",
                    "tools": ["github.issue", "mcp.tool"],
                },
            },
            {
                "id": "mcp_tool_probe",
                "kind": "tool",
                "adapter": "mcp.tool",
                "purpose": "Preview a local repository inspection tool without invoking it.",
                "inputs": {
                    "server": "local-repository-tools",
                    "tool_name": "inspect_repository",
                    "arguments": {"path": ".", "mode": "dry_run"},
                },
            },
            {
                "id": "verification_runner",
                "kind": "workflow",
                "adapter": "github.actions",
                "purpose": "Preview test workflow dispatch evidence without running a workflow.",
                "inputs": {
                    "repository": repository,
                    "workflow_ref": ".github/workflows/tests.yml",
                    "ref": "main",
                    "inputs": {"mode": "dry_run"},
                },
            },
            {
                "id": "risk_classifier",
                "kind": "ml_model",
                "adapter": "local.classifier",
                "model": "local_policy_model",
                "purpose": "Classify mission risk before any live execution.",
                "inputs": {
                    "profile": "delegation.default",
                    "plan": "Preview agent planning, MCP tools, and workflow dispatch with ledger evidence.",
                    "policy": "Require approval before live writes, tool execution, workflow dispatch, or external messages.",
                },
            },
            {
                "id": "maintainer_signoff",
                "kind": "human",
                "adapter": "human.approval",
                "purpose": "Require a human checkpoint before live execution.",
                "inputs": {
                    "approver": owner,
                    "request": "Approve moving this demo mission from dry-run evidence to live execution.",
                },
            },
        ],
        "policies": {
            "approvals": {"required_for": ["agent_execution", "external_message"]},
            "budgets": {"max_usd_per_run": 2, "max_minutes_per_run": 15},
            "permissions": {
                "allowed_repositories": [repository],
                "allowed_mcp_servers": ["local-repository-tools"],
                "allowed_mcp_tools": ["local-repository-tools/inspect_repository"],
                "network": "restricted",
            },
        },
        "outputs": [
            {"type": "github.issue"},
            {"type": "model_response"},
            {"type": "tool_result"},
            {"type": "test_result"},
            {"type": "approval"},
            {"type": "run_ledger"},
            {"type": "eval_report"},
        ],
        "evals": [
            {
                "id": "ledger_is_valid",
                "type": "invariant",
                "description": "The demo ledger must be readable and ordered.",
            },
            {
                "id": "required_adapter_evidence",
                "type": "invariant",
                "description": "Adapters must leave contract evidence before trust increases.",
            },
            {
                "id": "mcp_tool_risk_review",
                "type": "policy",
                "description": "MCP tool plans must expose permission and prompt-injection risk.",
            },
            {
                "id": "approvals_before_risky_actions",
                "type": "policy",
                "description": "Live risky actions require prior human approval evidence.",
            },
        ],
        "metadata": {
            "demo": True,
            "trust_boundary": "AI proposes; DelegationHQ verifies; humans approve risky actions.",
        },
    }


def build_demo_report(
    *,
    ledger_path: Path,
    harnessfile: Path | None = None,
    repository: str = DEFAULT_REPOSITORY,
    owner: str = "maintainer",
) -> DemoReport:
    if harnessfile:
        manifest = load_manifest(harnessfile)
        harness_source = str(harnessfile)
    else:
        manifest = build_demo_manifest(repository=repository, owner=owner)
        harness_source = "built-in demo"

    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("; ".join(errors))

    plan = compile_plan(manifest, source=harness_source)
    events = build_dry_run_ledger(plan)
    write_jsonl(events, ledger_path)
    event_dicts = [event.to_dict() for event in events]
    ledger_source = str(ledger_path)

    mcp_report = build_mcp_policy_report(manifest, plan, event_dicts, ledger_source=ledger_source)
    actions_report = build_actions_apply_report(
        manifest,
        plan,
        event_dicts,
        ledger_source=ledger_source,
        apply=False,
    )
    eval_results = tuple(run_declared_evals(manifest, event_dicts))
    ledger_view = build_ledger_view(
        event_dicts,
        source=ledger_source,
        ledger_filter=LedgerFilter(),
        limit=6,
    )

    eval_passed = sum(1 for result in eval_results if result.status == "passed")
    eval_attention = len(eval_results) - eval_passed
    steps = (
        FirstRunStep("plan", "passed", f"{len(plan.actions)} dry-run actions compiled."),
        FirstRunStep("ledger", "passed", f"{ledger_view.total_events} evidence events written."),
        FirstRunStep("mcp-gate", "blocked" if mcp_report.blocked else "passed", f"MCP policy gate is {mcp_report.status}."),
        FirstRunStep(
            "actions-preview",
            "blocked" if actions_report.blocked else "passed",
            f"GitHub Actions preview is {actions_report.status}.",
        ),
        FirstRunStep("evals", "passed" if eval_attention == 0 else "attention", f"{eval_passed} passed, {eval_attention} need attention."),
    )
    blocked = mcp_report.blocked or actions_report.blocked or any(step.status == "blocked" for step in steps)
    return DemoReport(
        status="blocked" if blocked else "ready",
        harness_source=harness_source,
        ledger_path=ledger_source,
        plan=plan,
        ledger_event_count=len(event_dicts),
        mcp_report=mcp_report,
        actions_report=actions_report,
        eval_results=eval_results,
        steps=steps,
    )


def render_demo_report(report: DemoReport) -> str:
    lines = [
        "DelegationHQ Demo",
        "",
        f"Status: {report.status}",
        f"Harnessfile: {report.harness_source}",
        f"Ledger: {report.ledger_path}",
        "",
        "What happened:",
    ]
    for step in report.steps:
        label = "PASS" if step.status == "passed" else "BLOCKED" if step.status == "blocked" else "CHECK"
        lines.append(f"- [{label}] {step.name}: {step.message}")

    lines.extend(
        [
            "",
            "What this proves:",
            "- AI work can be planned before it runs.",
            "- MCP tools can be allowlisted and risk-checked.",
            "- GitHub Actions can be previewed before dispatch.",
            "- Ledger evidence and evals decide what earns trust.",
            "",
            "Next:",
            f"delegation ledger {report.ledger_path}",
            f"delegation dashboard {report.ledger_path}",
            'delegation init --goal "prepare this repo for safe AI delegation"',
        ]
    )
    return "\n".join(lines)


def write_init_harnessfile(
    *,
    output_path: Path,
    goal: str = DEFAULT_INIT_GOAL,
    repository: str | None = None,
    owner: str | None = None,
    template: str | None = None,
    force: bool = False,
    plan: bool = False,
    ledger_path: Path | None = None,
) -> InitReport:
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} already exists. Use --force to overwrite it.")

    resolved_repository = repository or detect_github_repository(Path.cwd()) or "local/repository"
    resolved_owner = owner or _owner_from_repository(resolved_repository)
    suggestion = build_suggestion(goal, repository=resolved_repository, owner=resolved_owner, template=template)
    errors = suggestion.validate()
    if errors:
        raise ValueError("; ".join(errors))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(manifest_to_yaml(suggestion.manifest), encoding="utf-8")

    action_count = 0
    if plan:
        target_ledger = ledger_path or Path(".delegation/init.jsonl")
        compiled = compile_plan(suggestion.manifest, source=str(output_path))
        write_jsonl(build_dry_run_ledger(compiled), target_ledger)
        action_count = len(compiled.actions)
        ledger_value = str(target_ledger)
    else:
        ledger_value = None

    return InitReport(
        status="ready",
        output_path=str(output_path),
        repository=resolved_repository,
        owner=resolved_owner,
        template_id=suggestion.template_id,
        harness_id=str(suggestion.manifest.get("id")),
        planned=plan,
        ledger_path=ledger_value,
        action_count=action_count,
    )


def render_init_report(report: InitReport) -> str:
    lines = [
        "Starter Harnessfile Created",
        "",
        f"Status: {report.status}",
        f"Written: {report.output_path}",
        f"Repository: {report.repository}",
        f"Owner: {report.owner}",
        f"Template: {report.template_id}",
        f"Harnessfile id: {report.harness_id}",
    ]
    if report.planned and report.ledger_path:
        lines.extend(
            [
                f"Dry-run actions: {report.action_count}",
                f"Ledger: {report.ledger_path}",
            ]
        )
    lines.extend(
        [
            "",
            "Next:",
            f"delegation validate {report.output_path}",
            f"delegation plan {report.output_path} --ledger .delegation/latest.jsonl",
            "delegation demo",
        ]
    )
    return "\n".join(lines)


def detect_github_repository(root: Path) -> str | None:
    git = shutil.which("git")
    if not git:
        return None
    try:
        result = subprocess.run(
            [git, "remote", "get-url", "origin"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return _parse_github_remote(result.stdout.strip())


def _parse_github_remote(remote: str) -> str | None:
    patterns = (
        r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
        r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
    )
    for pattern in patterns:
        match = re.match(pattern, remote)
        if match:
            return f"{match.group('owner')}/{match.group('repo')}"
    return None


def _owner_from_repository(repository: str) -> str:
    owner = repository.split("/", 1)[0].strip()
    return owner or "maintainer"
