# GitHub Issue Apply Gate

`delegation apply-issues` is the first live execution gate.

Caveman version:

```text
Bot show issue first.
Bot check ledger.
Bot check policy.
Human say exact magic words.
Bot writes GitHub Issue.
Ledger keeps proof.
```

## Why This Exists

DelegationHQ should become powerful carefully. A live GitHub Issue is useful
coordination, but it is still a real write. So the command is preview-first and
gated.

This command only applies `github.issue` actions. It does not run agents, call
models, dispatch workflows, open pull requests, send messages, or deploy code.

## Preview

Run a dry-run plan first:

```bash
delegation plan Harnessfile.yaml --ledger .delegation/latest.jsonl
```

Preview the apply gates:

```bash
delegation apply-issues Harnessfile.yaml --ledger .delegation/latest.jsonl
```

Preview mode does not write to GitHub and does not need a token.

## Live Apply

Live apply requires:

- valid Harnessfile
- dry-run ledger
- passing ledger validity eval
- passing duplicate issue marker eval
- passing required adapter evidence eval
- repository allowed by policy
- explicit `--apply`
- exact confirmation token
- `GITHUB_TOKEN` or `GH_TOKEN`

```bash
GITHUB_TOKEN=... delegation apply-issues Harnessfile.yaml \
  --ledger .delegation/latest.jsonl \
  --apply \
  --confirm LIVE_GITHUB_ISSUES
```

If a matching issue marker already exists in the first 100 repository issues,
the command updates that issue. Otherwise it creates a new issue.

To inspect a normal applied lifecycle without touching GitHub, use the applied
fixture:

```bash
delegation ledger examples/ledgers/github-issue-applied.jsonl --adapter github.issue
```

To inspect an eval feedback issue that remembers its live GitHub issue link,
use the feedback memory fixture:

```bash
delegation ledger examples/ledgers/feedback-issue-memory.jsonl --adapter github.issue
```

## Ledger Events

Live apply appends events to the same ledger:

- `github.issue.apply.started`
- `github.issue.created` or `github.issue.updated`
- `github.issue.apply.failed`
- `github.issue.apply.completed`

Each event includes the adapter id, repository, issue marker, title, body
preview, and issue URL or number when GitHub returns it.

Those live issue fields are not just display metadata. The eval feedback loop
uses them so repeated failures can draft updates to the existing issue instead
of creating duplicate issue noise.

## Feedback Recovery Apply

When a failed eval later passes, use `recover-feedback` to draft the recovery
evidence, then use `apply-feedback` to preview the live comment:

```bash
delegation apply-feedback Harnessfile.yaml --ledger .delegation/latest.jsonl
```

Comment-only live apply requires:

```bash
GITHUB_TOKEN=... delegation apply-feedback Harnessfile.yaml \
  --ledger .delegation/latest.jsonl \
  --apply \
  --confirm LIVE_FEEDBACK_ISSUES
```

To close the issue after the recovery comment succeeds, use the stronger close
confirmation:

```bash
GITHUB_TOKEN=... delegation apply-feedback Harnessfile.yaml \
  --ledger .delegation/latest.jsonl \
  --apply \
  --close \
  --confirm CLOSE_FEEDBACK_ISSUES
```

`apply-feedback` appends:

- `github.issue.feedback_apply.started`
- `github.issue.comment.created`
- `github.issue.closed` when `--close` is used
- `github.issue.feedback_apply.failed`
- `github.issue.feedback_apply.completed`

This separates creating feedback issues from resolving them, so a user can
comment with proof without accidentally closing work.

## Safety Notes

- Dry-run remains the default.
- The confirmation string is intentionally loud.
- Unknown adapters are ignored by this command.
- GitHub token problems block before writing.
- Repository policy problems block before writing.
- Approval policy can require `approval.granted` ledger evidence for
  `github_issue`, `github.issue`, or `issue`.
