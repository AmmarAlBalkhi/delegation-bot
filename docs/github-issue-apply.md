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

Delegation Bot should become powerful carefully. A live GitHub Issue is useful
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

## Ledger Events

Live apply appends events to the same ledger:

- `github.issue.apply.started`
- `github.issue.created` or `github.issue.updated`
- `github.issue.apply.failed`
- `github.issue.apply.completed`

Each event includes the adapter id, repository, issue marker, title, body
preview, and issue URL or number when GitHub returns it.

## Safety Notes

- Dry-run remains the default.
- The confirmation string is intentionally loud.
- Unknown adapters are ignored by this command.
- GitHub token problems block before writing.
- Repository policy problems block before writing.
- Approval policy can require `approval.granted` ledger evidence for
  `github_issue`, `github.issue`, or `issue`.
