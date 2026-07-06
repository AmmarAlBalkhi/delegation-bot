"""Draft Harnessfiles from plain-language goals."""

from __future__ import annotations

import re
import typing as T
from dataclasses import dataclass

from delegation_bot.harness_manifest import Manifest, validate_manifest


DEFAULT_REPOSITORY = "AmmarAlBalkhi/delegation-bot"
DEFAULT_OWNER = "AmmarAlBalkhi"
SUGGESTION_TEMPLATE_IDS = (
    "release-readiness",
    "ci-repair",
    "documentation-refresh",
    "code-review",
    "weekly-planning",
    "general-agentic-work",
)


@dataclass(frozen=True)
class HarnessSuggestion:
    goal: str
    template_id: str
    template_reason: str
    manifest: Manifest

    def validate(self) -> list[str]:
        return validate_manifest(self.manifest)


def slugify_goal(goal: str, *, max_length: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", goal.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        return "ai-mission"
    if len(slug) <= max_length:
        return slug
    trimmed = slug[:max_length].strip("-")
    return trimmed or "ai-mission"


def infer_template(goal: str) -> tuple[str, str]:
    normalized = goal.lower()
    keyword_groups: list[tuple[str, tuple[str, ...], str]] = [
        (
            "release-readiness",
            ("release", "publish", "package", "pypi", "version", "changelog"),
            "The goal sounds like release or package readiness.",
        ),
        (
            "ci-repair",
            ("ci", "test", "failing", "failure", "build", "workflow", "actions"),
            "The goal sounds like verification or CI repair.",
        ),
        (
            "documentation-refresh",
            ("doc", "readme", "docs", "documentation", "guide", "explain"),
            "The goal sounds like documentation work.",
        ),
        (
            "code-review",
            ("review", "pr", "pull request", "diff", "change"),
            "The goal sounds like code review or pull request work.",
        ),
        (
            "weekly-planning",
            ("plan", "planning", "weekly", "roadmap", "prioritize", "priorities"),
            "The goal sounds like planning and prioritization.",
        ),
    ]
    for template_id, keywords, reason in keyword_groups:
        if any(_matches_keyword(normalized, keyword) for keyword in keywords):
            return template_id, reason
    return "general-agentic-work", "No narrow template matched, so a general safe delegation mission was selected."


def _matches_keyword(text: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text
    return bool(re.search(rf"\b{re.escape(keyword)}\b", text))


def build_suggestion(
    goal: str,
    *,
    repository: str = DEFAULT_REPOSITORY,
    owner: str = DEFAULT_OWNER,
    template: str | None = None,
) -> HarnessSuggestion:
    clean_goal = " ".join(goal.split()).strip()
    if not clean_goal:
        raise ValueError("goal must be a non-empty string")

    inferred_template, reason = infer_template(clean_goal)
    template_id = template or inferred_template
    builders: dict[str, T.Callable[[str, str, str], Manifest]] = {
        "release-readiness": _release_readiness_manifest,
        "ci-repair": _ci_repair_manifest,
        "documentation-refresh": _documentation_manifest,
        "code-review": _code_review_manifest,
        "weekly-planning": _weekly_planning_manifest,
        "general-agentic-work": _general_manifest,
    }
    if template_id not in builders:
        raise ValueError(f"unknown suggestion template `{template_id}`")
    manifest = builders[template_id](clean_goal, repository, owner)
    return HarnessSuggestion(
        goal=clean_goal,
        template_id=template_id,
        template_reason=reason if template is None else f"Template explicitly selected: {template_id}.",
        manifest=manifest,
    )


def manifest_to_yaml(manifest: Manifest) -> str:
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency is required by package metadata
        raise RuntimeError("PyYAML is required to render suggested Harnessfiles") from exc
    return yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False, width=88)


def render_suggestion(suggestion: HarnessSuggestion, *, output_path: str | None = None) -> str:
    manifest = suggestion.manifest
    lines = [
        "Suggested Harnessfile",
        "",
        f"Goal: {suggestion.goal}",
        f"Template: {suggestion.template_id}",
        f"Reason: {suggestion.template_reason}",
        f"Harnessfile id: {manifest.get('id')}",
        "",
        "Trust boundary:",
        "- AI or templates may propose this Harnessfile.",
        "- DelegationHQ must validate and dry-run it before execution.",
        "- Humans still approve risky actions.",
        "- Ledgers and evals decide whether trust increases.",
    ]
    if output_path:
        lines.extend(["", f"Written: {output_path}"])
    lines.extend(
        [
            "",
            "Next:",
            f"delegation validate {output_path or '<suggested-harnessfile.yaml>'}",
            f"delegation plan {output_path or '<suggested-harnessfile.yaml>'} --ledger .delegation/latest.jsonl",
        ]
    )
    return "\n".join(lines)


def _base_manifest(goal: str, repository: str, owner: str, template_id: str) -> Manifest:
    slug = slugify_goal(goal)
    return {
        "version": "delegation.ai/v1",
        "id": f"suggest-{slug}",
        "name": f"Suggested Mission: {slug.replace('-', ' ').title()}",
        "objective": goal,
        "triggers": [{"type": "manual"}],
        "owners": {"accountable": owner, "reviewers": [owner]},
        "models": [
            {
                "id": "planner_model",
                "provider": "openai",
                "model": "gpt-5.5",
                "role": "planning",
                "budget_usd": 2,
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
                "description": "Read repository files, docs, issues, package metadata, and prior ledgers.",
                "capabilities": [
                    "read.repository",
                    "read.github_issues",
                    "read.run_ledger",
                ],
            },
            {
                "id": "mission_drafter",
                "description": "Draft plans, issues, notes, and pull request text without publishing.",
                "capabilities": [
                    "write.plan_draft",
                    "write.issue_draft",
                    "write.pull_request_draft",
                ],
                "approval_required_for": [
                    "publish.issue",
                    "publish.pull_request",
                ],
            },
            {
                "id": "policy_reviewer",
                "description": "Classify risk and suggest approval or evidence requirements.",
                "capabilities": [
                    "read.plan",
                    "classify.risk",
                    "suggest.policy",
                ],
            },
        ],
        "agents": [
            {
                "id": "mission_planner",
                "runtime": "openai.agents",
                "model": "planner_model",
                "autonomy_level": "draft",
                "capability_packs": [
                    "repo_reader",
                    "mission_drafter",
                    "policy_reviewer",
                ],
                "promotion": {
                    "next_level": "act",
                    "requires_evals": [
                        "approvals_before_risky_actions",
                        "required_adapter_evidence",
                    ],
                },
            },
            {
                "id": "policy_guard",
                "runtime": "local.classifier",
                "model": "local_policy_model",
                "autonomy_level": "suggest",
                "capability_packs": [
                    "policy_reviewer",
                ],
            },
        ],
        "context": {
            "sources": [
                {"id": "repository", "kind": "git", "trust": "high"},
                {"id": "user_goal", "kind": "human", "trust": "medium"},
                {"id": "prior_ledgers", "kind": "run_ledger", "trust": "medium"},
            ]
        },
        "policies": {
            "approvals": {
                "required_for": [
                    "agent_execution",
                    "pull_request",
                    "workflow",
                ]
            },
            "budgets": {
                "max_usd_per_run": 5,
                "max_minutes_per_run": 45,
            },
            "permissions": {
                "allowed_repositories": [repository],
                "network": "restricted",
            },
        },
        "outputs": [
            {"type": "github.issue"},
            {"type": "approval"},
            {"type": "run_ledger"},
            {"type": "eval_report"},
        ],
        "evals": [
            {
                "id": "no_duplicate_issue_markers",
                "type": "invariant",
                "description": "The suggested mission must not create duplicate tracking issues.",
            },
            {
                "id": "approvals_before_risky_actions",
                "type": "policy",
                "description": "Executed risky actions require human approval evidence.",
            },
            {
                "id": "required_adapter_evidence",
                "type": "invariant",
                "description": "SDK-backed adapters must leave required contract evidence and outputs.",
            },
        ],
        "metadata": {
            "suggested_by": "delegation.suggest",
            "suggestion_template": template_id,
            "trust_boundary": "AI proposes; DelegationHQ verifies; humans approve risky actions.",
        },
    }


def _release_readiness_manifest(goal: str, repository: str, owner: str) -> Manifest:
    manifest = _base_manifest(goal, repository, owner, "release-readiness")
    manifest["executors"] = [
        _issue_executor(
            repository,
            "Suggested mission: release readiness",
            "Track package metadata, license, changelog, docs, QA, artifacts, and approval gates before release.",
        ),
        _echo_executor(
            "release-readiness",
            "Release readiness suggestion drafted without live model or GitHub writes.",
        ),
        _risk_executor("Verify release risk before any publication step.", profile="release-readiness"),
        {
            "id": "qa_workflow",
            "kind": "workflow",
            "adapter": "github.actions",
            "purpose": "Plan test workflow execution and collect status evidence.",
            "inputs": {"repository": repository, "workflow_ref": ".github/workflows/tests.yml"},
        },
        _approval_executor(owner, "Approve release readiness evidence before publication."),
    ]
    manifest["outputs"].insert(1, {"type": "test_result"})
    manifest["evals"].append(
        {
            "id": "tests_pass_before_pr",
            "type": "quality_gate",
            "description": "Pull requests require a passing test event in the run ledger.",
        }
    )
    return manifest


def _ci_repair_manifest(goal: str, repository: str, owner: str) -> Manifest:
    manifest = _base_manifest(goal, repository, owner, "ci-repair")
    manifest["executors"] = [
        _issue_executor(
            repository,
            "Suggested mission: CI repair",
            "Track failing checks, suspected cause, repair plan, test evidence, and approval.",
        ),
        _risk_executor("Classify the CI repair risk before implementation."),
        _codex_executor(repository, "Draft a scoped CI repair after approval evidence exists."),
        {
            "id": "verification_workflow",
            "kind": "workflow",
            "adapter": "github.actions",
            "purpose": "Plan the verification workflow and collect test evidence.",
            "inputs": {"repository": repository, "workflow_ref": ".github/workflows/tests.yml"},
        },
        _approval_executor(owner, "Approve the CI repair plan before any pull request is published."),
    ]
    manifest["outputs"].insert(1, {"type": "test_result"})
    manifest["outputs"].insert(2, {"type": "github.pull_request"})
    manifest["evals"].append(
        {
            "id": "tests_pass_before_pr",
            "type": "quality_gate",
            "description": "Pull requests require a passing test event in the run ledger.",
        }
    )
    return manifest


def _documentation_manifest(goal: str, repository: str, owner: str) -> Manifest:
    manifest = _base_manifest(goal, repository, owner, "documentation-refresh")
    manifest["executors"] = [
        _issue_executor(
            repository,
            "Suggested mission: documentation refresh",
            "Track documentation goals, scope, evidence, and approval.",
        ),
        _echo_executor("documentation-refresh", "Documentation mission suggestion drafted with no live writes."),
        _codex_executor(repository, "Draft scoped documentation updates after approval evidence exists."),
        _approval_executor(owner, "Approve the documentation plan before publishing changes."),
    ]
    manifest["outputs"].insert(1, {"type": "github.pull_request"})
    return manifest


def _code_review_manifest(goal: str, repository: str, owner: str) -> Manifest:
    manifest = _base_manifest(goal, repository, owner, "code-review")
    manifest["models"].append(
        {
            "id": "claude_reviewer_model",
            "provider": "anthropic",
            "adapter": "anthropic.messages",
            "model": "claude-sonnet",
            "role": "review",
            "budget_usd": 2,
        }
    )
    manifest["agents"].append(
        {
            "id": "claude_reviewer",
            "runtime": "claude.code",
            "model": "claude_reviewer_model",
            "autonomy_level": "draft",
            "capability_packs": [
                "repo_reader",
                "mission_drafter",
                "policy_reviewer",
            ],
            "promotion": {
                "next_level": "act",
                "requires_evals": [
                    "approvals_before_risky_actions",
                    "required_adapter_evidence",
                ],
            },
        }
    )
    manifest["executors"] = [
        _issue_executor(
            repository,
            "Suggested mission: code review",
            "Track review scope, risk, findings, and required evidence.",
        ),
        {
            "id": "review_agent",
            "kind": "ai_harness",
            "adapter": "claude.code",
            "model": "claude_reviewer_model",
            "purpose": "Plan a code review pass without applying changes.",
            "inputs": {
                "objective": goal,
                "repository": repository,
                "allowed_files": ["delegation_bot/**", "scripts/**", "tests/**", "docs/**"],
                "mcp_servers": [],
            },
        },
        _approval_executor(owner, "Approve any review-driven change before publication."),
    ]
    manifest["outputs"].insert(1, {"type": "agent_result"})
    return manifest


def _weekly_planning_manifest(goal: str, repository: str, owner: str) -> Manifest:
    manifest = _base_manifest(goal, repository, owner, "weekly-planning")
    manifest["executors"] = [
        _issue_executor(
            repository,
            "Suggested mission: planning",
            "Track priorities, owners, blockers, and follow-up evidence.",
        ),
        _echo_executor("weekly-planning", "Planning suggestion drafted with no live writes."),
        {
            "id": "planning_agent",
            "kind": "ai_harness",
            "adapter": "openai.agents",
            "model": "planner_model",
            "purpose": "Draft planning priorities from repository context without applying changes.",
            "inputs": {
                "model": "gpt-5.5",
                "instructions": "Suggest focused weekly priorities with owners, evidence, and approval gates.",
                "tools": ["github.issue"],
            },
        },
        _approval_executor(owner, "Approve the planning output before it is treated as accepted."),
    ]
    manifest["outputs"].insert(1, {"type": "agent_result"})
    return manifest


def _general_manifest(goal: str, repository: str, owner: str) -> Manifest:
    manifest = _base_manifest(goal, repository, owner, "general-agentic-work")
    manifest["executors"] = [
        _issue_executor(
            repository,
            "Suggested mission: agentic work",
            "Track the goal, dry-run plan, risks, evidence, and approval gates.",
        ),
        _echo_executor("general-agentic-work", "General mission suggestion drafted with no live writes."),
        _risk_executor("Classify the suggested mission risk before any live action."),
        _approval_executor(owner, "Approve the suggested mission before live execution."),
    ]
    return manifest


def _issue_executor(repository: str, title: str, body: str) -> dict[str, T.Any]:
    return {
        "id": "mission_issue",
        "kind": "workflow",
        "adapter": "github.issue",
        "purpose": "Open or update a tracking issue for the suggested mission.",
        "inputs": {
            "repository": repository,
            "issue_title": title,
            "issue_body": body,
        },
    }


def _echo_executor(label: str, message: str) -> dict[str, T.Any]:
    return {
        "id": "suggestion_receipt",
        "kind": "tool",
        "adapter": "sample.echo",
        "purpose": "Leave no-network evidence that the suggestion was generated.",
        "inputs": {
            "label": label,
            "message": message,
        },
    }


def _risk_executor(plan: str, *, profile: str = "delegation.default") -> dict[str, T.Any]:
    return {
        "id": "risk_classifier",
        "kind": "ml_model",
        "adapter": "local.classifier",
        "model": "local_policy_model",
        "purpose": "Classify plan risk before execution.",
        "inputs": {
            "profile": profile,
            "plan": plan,
            "policy": "Require approvals for agent execution, workflows, pull requests, and external messages.",
        },
    }


def _codex_executor(repository: str, objective: str) -> dict[str, T.Any]:
    return {
        "id": "implementation_agent",
        "kind": "ai_harness",
        "adapter": "codex.thread",
        "model": "planner_model",
        "purpose": "Draft scoped repository changes after approval.",
        "inputs": {
            "objective": objective,
            "repository": repository,
            "allowed_files": [
                "delegation_bot/**",
                "scripts/**",
                "tests/**",
                "docs/**",
                "README.md",
                "CHANGELOG.md",
            ],
        },
    }


def _approval_executor(owner: str, request: str) -> dict[str, T.Any]:
    return {
        "id": "maintainer_signoff",
        "kind": "human",
        "adapter": "human.approval",
        "purpose": "Require maintainer approval before live execution.",
        "inputs": {
            "approver": owner,
            "request": request,
        },
    }
