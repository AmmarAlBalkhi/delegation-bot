"""GitHub App permission and installation-token planning."""

from __future__ import annotations

import json
import typing as T
from dataclasses import dataclass
from pathlib import Path


MODE_READ_ONLY = "read-only"
MODE_ISSUE_WRITE = "issue-write"
MODE_ACTIONS_CONTROL = "actions-control"
MODE_CHOICES = (MODE_READ_ONLY, MODE_ISSUE_WRITE, MODE_ACTIONS_CONTROL)


@dataclass(frozen=True)
class GitHubAppPermission:
    name: str
    access: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "access": self.access,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class GitHubAppPlan:
    mode: str
    repository: str | None
    permissions: list[GitHubAppPermission]
    webhook_events: list[str]
    token_request: dict[str, T.Any]
    safety_rules: list[str]
    next_steps: list[str]

    def to_dict(self) -> dict[str, T.Any]:
        return {
            "mode": self.mode,
            "repository": self.repository,
            "permissions": [permission.to_dict() for permission in self.permissions],
            "webhook_events": self.webhook_events,
            "token_request": self.token_request,
            "safety_rules": self.safety_rules,
            "next_steps": self.next_steps,
        }


def build_github_app_plan(mode: str = MODE_READ_ONLY, *, repository: str | None = None) -> GitHubAppPlan:
    if mode not in MODE_CHOICES:
        raise ValueError(f"unknown GitHub App mode: {mode}")

    permissions = _permissions_for_mode(mode)
    webhook_events = _webhooks_for_mode(mode)
    token_request: dict[str, T.Any] = {
        "installation_id": "<installation_id>",
        "endpoint": "POST /app/installations/{installation_id}/access_tokens",
        "repositories": [repository] if repository else ["<selected repositories>"],
        "permissions": {permission.name: permission.access for permission in permissions if permission.name != "metadata"},
        "expires_after": "1 hour",
        "notes": [
            "Token permissions cannot exceed the GitHub App registration permissions.",
            "Token repository access cannot exceed the selected installation repositories.",
            "DelegationHQ should request only the mode needed for the approved action.",
        ],
    }

    return GitHubAppPlan(
        mode=mode,
        repository=repository,
        permissions=permissions,
        webhook_events=webhook_events,
        token_request=token_request,
        safety_rules=[
            "Dry-run remains the default.",
            "A GitHub App token does not bypass policy gates.",
            "Live writes still require explicit confirmation.",
            "Every live write must append ledger evidence.",
            "Private keys, webhook secrets, and installation tokens stay outside the repository.",
        ],
        next_steps=_next_steps_for_mode(mode),
    )


def render_github_app_plan(plan: GitHubAppPlan) -> str:
    lines = [
        "GitHub App Plan",
        "",
        f"Mode: {plan.mode}",
        f"Repository: {plan.repository or '<selected repositories>'}",
        "",
        "Permissions:",
    ]
    for permission in plan.permissions:
        lines.append(f"- {permission.name}: {permission.access} - {permission.reason}")

    lines.extend(["", "Webhook events:"])
    lines.extend(f"- {event}" for event in plan.webhook_events)

    lines.extend(["", "Installation token request shape:"])
    lines.append(json.dumps(plan.token_request, indent=2, sort_keys=True))

    lines.extend(["", "Safety rules:"])
    lines.extend(f"- {rule}" for rule in plan.safety_rules)

    lines.extend(["", "Next:"])
    lines.extend(f"- {step}" for step in plan.next_steps)
    return "\n".join(lines)


def write_github_app_plan(plan: GitHubAppPlan, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _permissions_for_mode(mode: str) -> list[GitHubAppPermission]:
    permissions = [
        GitHubAppPermission("metadata", "read", "Required baseline repository metadata access."),
        GitHubAppPermission("contents", "read", "Read Harnessfiles and release metadata when imported from a repository."),
        GitHubAppPermission("issues", "read", "Read existing issue context and feedback markers."),
        GitHubAppPermission("pull_requests", "read", "Read pull request context for planning and eval evidence."),
        GitHubAppPermission("actions", "read", "Read workflow run status and artifact evidence."),
        GitHubAppPermission("checks", "read", "Read check status when eval evidence needs CI state."),
    ]
    if mode == MODE_ISSUE_WRITE:
        permissions = _replace_permission(
            permissions,
            GitHubAppPermission("issues", "write", "Create or update approved feedback issues."),
        )
    elif mode == MODE_ACTIONS_CONTROL:
        permissions = _replace_permission(
            permissions,
            GitHubAppPermission("actions", "write", "Dispatch or cancel approved workflow runs."),
        )
    return permissions


def _replace_permission(
    permissions: list[GitHubAppPermission],
    replacement: GitHubAppPermission,
) -> list[GitHubAppPermission]:
    return [replacement if permission.name == replacement.name else permission for permission in permissions]


def _webhooks_for_mode(mode: str) -> list[str]:
    events = ["installation", "installation_repositories"]
    if mode in (MODE_READ_ONLY, MODE_ISSUE_WRITE):
        events.extend(["issues", "issue_comment", "pull_request", "workflow_run"])
    if mode == MODE_ACTIONS_CONTROL:
        events.extend(["workflow_run", "check_run"])
    return sorted(set(events))


def _next_steps_for_mode(mode: str) -> list[str]:
    if mode == MODE_READ_ONLY:
        return [
            "Register the app with read-only permissions first.",
            "Install it on selected repositories only.",
            "Use imported ledgers and dry-run commands before any live write mode.",
        ]
    if mode == MODE_ISSUE_WRITE:
        return [
            "Enable issue-write only after feedback drafts are useful in preview mode.",
            "Keep `delegation apply-issues --apply --confirm LIVE_GITHUB_ISSUES` as the live gate.",
            "Record created or updated issue numbers in the run ledger.",
        ]
    return [
        "Enable actions-control only after issue-write mode is stable.",
        "Keep workflow dispatch and cancellation behind exact confirmation tokens.",
        "Require ledger idempotency checks before dispatching workflows.",
    ]
