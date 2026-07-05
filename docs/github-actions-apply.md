# GitHub Actions Apply Gate

`delegation apply-actions` previews a gated GitHub Actions workflow dispatch.

Caveman version:

```text
Bot show workflow.
Bot show branch.
Bot show inputs.
Bot check ledger and policy.
Bot does not press run yet.
```

## Why This Exists

GitHub Actions is where many repositories already run tests, release jobs, and
automation. That makes it powerful and risky. A bad workflow dispatch can burn
minutes, publish artifacts, deploy code, or trigger other automation.

So the first useful slice is a dispatch preview, not live dispatch.

## Preview

Run a dry-run plan first:

```bash
delegation plan Harnessfile.yaml --ledger .delegation/latest.jsonl
```

Preview the workflow dispatch gates:

```bash
delegation apply-actions Harnessfile.yaml --ledger .delegation/latest.jsonl
```

Preview mode does not call GitHub and does not need a token. It shows:

- repository
- workflow file
- ref, defaulting to `main` when the Harnessfile does not declare one
- workflow input keys and redacted input values
- dry-run workflow run id
- dry-run workflow run URL shape
- policy, approval, ledger, and intent gates

## Live Dispatch Status

Live GitHub Actions dispatch is intentionally locked for now.

Even this command blocks:

```bash
delegation apply-actions Harnessfile.yaml \
  --ledger .delegation/latest.jsonl \
  --apply \
  --confirm LIVE_GITHUB_ACTIONS
```

That is deliberate. The preview gate should prove the workflow draft and
evidence shape before a live dispatch client exists.

## Gates

The preview checks:

- valid Harnessfile
- dry-run ledger exists
- ledger validity eval passes
- required adapter evidence eval passes
- each workflow draft has matching ledger evidence
- each workflow draft has a run URL preview
- repository is allowed by policy
- workflow approval evidence exists when policy requires `workflow`,
  `github.actions`, `github_actions`, `workflow_dispatch`, or `actions`
- live dispatch is not being silently attempted

## Fixture

Inspect the no-network lifecycle:

```bash
delegation ledger examples/ledgers/github-actions-preview.jsonl --adapter github.actions
```

The fixture shows a planned workflow dispatch with `workflow_run_id`,
`workflow_run_url`, and approval evidence, without running GitHub Actions.

## GitHub API Notes

GitHub's REST API exposes workflow dispatch as a manual trigger for workflows
configured with `workflow_dispatch`. A dispatch request needs a workflow id or
file name, a `ref`, optional inputs, and appropriate repository access. Workflow
run APIs then expose run status, logs, reruns, and cancellation.

Sources checked on 2026-07-05:

- [GitHub REST workflow dispatch docs](https://docs.github.com/en/rest/actions/workflows)
- [GitHub REST workflow runs docs](https://docs.github.com/en/rest/actions/workflow-runs)
- [GitHub workflow_dispatch syntax docs](https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions)
- [GitHub manual workflow run docs](https://docs.github.com/actions/managing-workflow-runs/manually-running-a-workflow)

## Future Live Client

The future live dispatch step should use the same gates, then add:

- token scope checks
- default-branch workflow-file check
- idempotency or duplicate-run protection
- run URL returned by GitHub when available
- appended `github.actions.dispatched` and status events
- cancellation guidance for failed or accidental runs

Until then, the correct behavior is boring and safe: preview, prove, stop.
