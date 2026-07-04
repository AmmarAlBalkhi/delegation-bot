# Live Execution Gate

This document designs the first safe step from dry-run planning toward live
execution.

Simple version: start with live GitHub Issue creation or update only. Do not
start with live model calls, live coding agents, external messages, workflow
runs, or deployments.

## Principle

Live execution must be earned by evidence.

The system should prove the plan first:

```text
validate -> plan -> ledger -> eval -> approval -> apply
```

No live action should bypass that loop.

## First Live Adapter

First candidate:

```text
github.issue
```

Why:

- visible and reversible compared with code execution
- already has an idempotent marker pattern
- useful for coordination even when all agent work stays dry-run
- easy for users to inspect in GitHub
- fits the existing legacy task bot behavior

## Explicit Non-Goals

Do not enable these in the first live gate:

- live coding-agent execution
- live model calls
- live MCP tool calls
- live GitHub Actions dispatch
- pull request creation
- external messages
- deployments

Those can come later after the live-gate pattern is proven.

## Required Gates

A live `github.issue` apply should require:

- valid Harnessfile
- compiled dry-run plan
- ledger written before apply
- `ledger_is_valid` passed
- `required_adapter_evidence` passed
- no duplicate issue marker failure
- explicit `--apply` or `APPLY=true`
- target repository allowed by policy
- `GITHUB_TOKEN` available
- dry-run issue body includes the ledger or artifact reference

If any required gate is missing, the command should explain what is missing and
stop before writing.

## Command Shape

Possible future command:

```bash
delegation run Harnessfile.yaml --apply --adapter github.issue
```

Safer first slice:

```bash
delegation apply-issues Harnessfile.yaml --ledger .delegation/latest.jsonl
```

The second shape is less elegant, but clearer while live execution is new.
This first slice is now implemented as a preview-first command. Live writes
require:

```bash
delegation apply-issues Harnessfile.yaml \
  --ledger .delegation/latest.jsonl \
  --apply \
  --confirm LIVE_GITHUB_ISSUES
```

See `docs/github-issue-apply.md` for the user-facing guide.

## Ledger Events

Live issue apply should append events such as:

```text
github.issue.apply.started
github.issue.created
github.issue.updated
github.issue.apply.blocked
github.issue.apply.failed
github.issue.apply.completed
```

Every event should include:

- adapter id
- repository
- issue marker
- issue number or URL when available
- source dry-run action id
- approval or apply mode evidence
- sanitized body preview

## Policy Behavior

The policy engine should treat issue creation as lower risk than agent
execution, but still live.

Recommended policy name:

```text
github_issue
```

If `github_issue` appears in `policies.approvals.required_for`, live issue apply
should require approval evidence in the ledger. If it does not appear, apply
mode and repository permission are still required.

## Failure Handling

Live apply should be boring and recoverable:

- repeated runs update the same marker instead of creating duplicates
- failed writes append failure evidence
- partial success is reported clearly
- no secrets are written to issue bodies
- dry-run remains the default

## Success Criteria

The first live gate is ready when:

- dry-run behavior is unchanged
- local QA passes
- a fixture ledger can show blocked, planned, and applied issue states
- documentation shows exactly how to preview before apply
- the command can run safely in GitHub Actions with `apply=false`
- live apply requires explicit user intent

## Why This Is The Right First Live Step

The project wins trust by moving carefully.

A live issue is visible coordination. A live coding agent is power. Coordination
should go live before power.
