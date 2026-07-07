# Live Execution Gate

This document designs the first safe step from dry-run planning toward live
execution.

Simple version: live actions must be earned by evidence. GitHub Issues proved
the first low-risk live gate; GitHub Actions now follows the same preview-first
pattern.

## Principle

Live execution must be earned by evidence.

The system should prove the plan first:

```text
validate -> plan -> ledger -> eval -> approval -> apply
```

No live action should bypass that loop.

## First Live Adapters

First candidate, now implemented:

```text
github.issue
```

Why:

- visible and reversible compared with code execution
- already has an idempotent marker pattern
- useful for coordination even when all agent work stays dry-run
- easy for users to inspect in GitHub
- fits the existing legacy task bot behavior

Second controlled live surface:

```text
github.actions
```

Why:

- repository-native verification and release automation already lives there
- the dispatch request has a small explicit shape: repository, workflow, ref,
  and inputs
- GitHub returns run identifiers and URLs that fit the ledger model
- risky workflow dispatch can be forced through approval policy first

## Explicit Non-Goals

Do not enable these until their gates are as clear as GitHub Issues and GitHub
Actions:

- live coding-agent execution
- live model calls
- live MCP tool calls
- pull request creation
- external messages
- deployments

Those can come later after their preview evidence, approval rules, failure
handling, and ledger events are boring enough to trust.

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
- `GITHUB_TOKEN`/`GH_TOKEN` or configured GitHub App issue-write auth
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

GitHub App auth can provide a scoped issue-write installation token:

```bash
delegation apply-issues Harnessfile.yaml \
  --ledger .delegation/latest.jsonl \
  --apply \
  --confirm LIVE_GITHUB_ISSUES \
  --auth github-app
```

See `docs/github-issue-apply.md` for the user-facing guide.

GitHub Actions dispatch preview:

```bash
delegation apply-actions Harnessfile.yaml --ledger .delegation/latest.jsonl
```

Live dispatch:

```bash
delegation apply-actions Harnessfile.yaml \
  --ledger .delegation/latest.jsonl \
  --apply \
  --confirm LIVE_GITHUB_ACTIONS
```

This requires `GITHUB_TOKEN` or `GH_TOKEN`. See `docs/github-actions-apply.md`.

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
- auth source, without the token value
- sanitized body preview

Live workflow dispatch appends:

```text
github.actions.dispatch.started
github.actions.dispatch.blocked
github.actions.dispatched
github.actions.dispatch.failed
github.actions.dispatch.completed
```

Every event should include:

- adapter id
- repository
- workflow file or id
- ref
- input keys, with sensitive values omitted
- workflow run id and URL when GitHub returns them
- source dry-run action id
- live preflight gates for workflow metadata and duplicate active runs
- cancellation API paths after dispatch

Live feedback recovery apply appends:

```text
github.issue.feedback_apply.started
github.issue.comment.created
github.issue.closed
github.issue.feedback_apply.failed
github.issue.feedback_apply.completed
```

Comment-only recovery apply requires `--apply --confirm
LIVE_FEEDBACK_ISSUES`. Closing a feedback issue after the recovery comment
requires `--apply --close --confirm CLOSE_FEEDBACK_ISSUES`.

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

## GitHub Actions Preview Criteria

The workflow dispatch preview is useful when:

- the dry-run ledger contains `github.actions` adapter evidence
- the evidence includes `workflow_run_id`, `workflow_run_url`, and conclusion
- the command shows repository, workflow file, ref, and input keys
- repository policy is checked before future dispatch
- approval policy can require `approval.granted` evidence for workflow actions
- live dispatch requires `--apply --confirm LIVE_GITHUB_ACTIONS` and a token
- live preflight confirms workflow metadata before dispatch
- active duplicate `workflow_dispatch` runs on the same ref block dispatch

## Why This Is The Right First Live Step

The project wins trust by moving carefully.

A live issue is visible coordination. A live coding agent is power. Coordination
should go live before power.
