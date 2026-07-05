# Ledger Fixtures

These compact JSONL fixtures show the adapter result states contributors need
to understand.

They live in `examples/ledgers/`:

- `adapter-good.jsonl`: adapter evidence is complete and should pass
- `adapter-blocked.jsonl`: adapter could not plan because input was missing
- `adapter-failed.jsonl`: adapter reported a failed result
- `github-issue-applied.jsonl`: a planned `github.issue` action was applied
  and recorded with issue evidence
- `github-actions-preview.jsonl`: a planned `github.actions` workflow dispatch
  has run URL and approval evidence without live dispatch
- `mcp-tool-risk.jsonl`: a planned `mcp.tool` call shows high-risk permission
  and prompt-injection evidence without invoking the tool
- `feedback-issue-memory.jsonl`: an eval feedback issue was created live, then
  a later matching failure drafted an update pointing at the same issue
- `feedback-recovery.jsonl`: a feedback issue later sees a passing eval and
  drafts a recovery update

## Why They Exist

Simple version: fixtures make the black-box recorder easy to learn.

Instead of running a full Harnessfile, a contributor can inspect one tiny ledger
and see how adapter evidence, outputs, statuses, and evals fit together.

## Inspect Them

Good evidence:

```bash
python scripts/delegation.py ledger examples/ledgers/adapter-good.jsonl --adapter sample.echo
```

Blocked result:

```bash
python scripts/delegation.py ledger examples/ledgers/adapter-blocked.jsonl --status blocked
```

Failed result:

```bash
python scripts/delegation.py ledger examples/ledgers/adapter-failed.jsonl --status failed
```

Applied GitHub Issue:

```bash
python scripts/delegation.py ledger examples/ledgers/github-issue-applied.jsonl --adapter github.issue
```

GitHub Actions dispatch preview:

```bash
python scripts/delegation.py ledger examples/ledgers/github-actions-preview.jsonl --adapter github.actions
```

MCP tool risk evidence:

```bash
python scripts/delegation.py ledger examples/ledgers/mcp-tool-risk.jsonl --adapter mcp.tool
```

Feedback issue memory:

```bash
python scripts/delegation.py ledger examples/ledgers/feedback-issue-memory.jsonl --adapter github.issue
```

Feedback recovery:

```bash
python scripts/delegation.py ledger examples/ledgers/feedback-recovery.jsonl --adapter github.issue
python scripts/delegation.py dashboard examples/ledgers/feedback-recovery.jsonl
```

## Eval Behavior

The `required_adapter_evidence` eval should:

- pass for `adapter-good.jsonl`
- block for `adapter-blocked.jsonl`
- fail for `adapter-failed.jsonl`

That gives adapter authors a quick sanity check for the three most important
states before they touch live execution.

## Fixture Rules

Keep fixtures:

- small enough to read in a minute
- valid JSONL, one event per line
- deterministic
- free of secrets
- free of network assumptions
- tied to real adapter contracts
- representative of real lifecycle states such as planned, blocked, failed,
  created, updated, and completed

These files are documentation and tests at the same time.

## Generate Fixtures

Use the generator when a new SDK-backed adapter needs repeatable examples:

```bash
python scripts/generate_adapter_fixtures.py mcp.tool --state good --output examples/ledgers/generated/adapter-mcp-tool-good.jsonl
python scripts/generate_adapter_fixtures.py sample.echo --state blocked --output examples/ledgers/generated/adapter-sample-echo-blocked.jsonl
python scripts/generate_adapter_fixtures.py --all --output-dir examples/ledgers/generated
```

The generated fixtures follow the same eval behavior:

- `good` should pass `required_adapter_evidence`
- `blocked` should block `required_adapter_evidence`
- `failed` should fail `required_adapter_evidence`
