# Dashboard Data Model

The first dashboard step is not a visual UI. It is a stable read-only snapshot
that a future UI can render.

Simple version:

```text
Ledger is black box.
Dashboard snapshot is cockpit data.
UI can come later.
```

## Command

```bash
python scripts/delegation.py dashboard examples/ledgers/feedback-recovery.jsonl
```

With Harnessfile context:

```bash
python scripts/delegation.py dashboard .delegation/latest.jsonl \
  --harnessfile examples/ai-harness-control-plane.yaml
```

For UI prototypes or hosted services:

```bash
python scripts/delegation.py dashboard .delegation/latest.jsonl \
  --harnessfile examples/ai-harness-control-plane.yaml \
  --json
```

## Snapshot Shape

The JSON snapshot includes:

- `mission`: id, objective, mode, repository, owners, reviewers
- `status`: `empty`, `planned`, `ready`, `blocked`, `failed`, or
  `needs_attention`
- `next_safe_action`: one plain-language next step
- `counts`: events, runs, adapters, evals, feedback items, agents, statuses
- `adapters`: adapter/action records with latest status and evidence keys
- `evals`: latest eval result per eval id
- `feedback`: latest feedback issue state per marker, including live issue links
- `agents`: agent runtime, model, autonomy level, and capability packs
- `warnings`: missing context or incomplete input signals

## Status Rule

The dashboard uses the latest eval state first.

- latest failed eval -> `failed`
- latest blocked eval -> `blocked`
- all latest evals passed -> `ready`
- historical failed events without current eval failure -> not automatically red

That lets the dashboard show recovery correctly: old failures remain visible in
the ledger, but a passing eval plus recovery draft can move the mission back to
ready.

## Product Boundary

This command is read-only:

- no GitHub writes
- no model calls
- no agent execution
- no workflow dispatch

The future hosted dashboard should consume this kind of snapshot before it gets
any live controls.
