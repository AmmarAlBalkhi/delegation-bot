# Ledger Viewer

The run ledger is Delegation Bot's black-box recorder.

Simple version: every plan, adapter action, eval result, approval, and future
live execution should leave an event in a JSONL ledger. The ledger viewer turns
that raw JSONL into a readable report.

## Command

```bash
python scripts/delegation.py ledger .delegation/latest.jsonl
```

After installing from source:

```bash
delegation ledger .delegation/latest.jsonl
```

## What It Shows

The report includes:

- total event count
- run ids
- status counts
- adapter counts
- adapter evidence from SDK-backed adapter results
- eval results
- recent events
- warnings for empty or malformed sequence patterns

The most important part is adapter evidence. That is where a dry-run adapter can
show what it planned, what outputs it would create, and what proof it left
behind.

## Evidence Eval

The built-in `required_adapter_evidence` eval checks SDK-backed adapter results.
It verifies that each adapter result:

- matches a known adapter contract
- includes every required evidence key
- includes every required output key except `run_ledger`
- reached a `planned` or `succeeded` state

This means the ledger is not only readable. It can also be judged.

## Useful Filters

Show events for one adapter:

```bash
python scripts/delegation.py ledger .delegation/latest.jsonl --adapter github.issue
```

Show the no-network sample adapter:

```bash
python scripts/delegation.py ledger .delegation/latest.jsonl --adapter sample.echo
```

Show one event type:

```bash
python scripts/delegation.py ledger .delegation/latest.jsonl --type github.issue.planned
```

Show blocked events:

```bash
python scripts/delegation.py ledger .delegation/latest.jsonl --status blocked
```

Show one action:

```bash
python scripts/delegation.py ledger .delegation/latest.jsonl --action executor.issue_planner
```

Print JSON for automation or a future dashboard:

```bash
python scripts/delegation.py ledger .delegation/latest.jsonl --json
```

## Fixtures

Compact fixture ledgers live in `examples/ledgers/`.

Use them when you want to inspect adapter states without running a full
Harnessfile:

```bash
python scripts/delegation.py ledger examples/ledgers/adapter-good.jsonl --adapter sample.echo
python scripts/delegation.py ledger examples/ledgers/adapter-blocked.jsonl --status blocked
python scripts/delegation.py ledger examples/ledgers/adapter-failed.jsonl --status failed
```

See `docs/ledger-fixtures.md`.

## Why This Matters

The core product loop is:

```text
Harnessfile -> dry-run plan -> policy gates -> adapter actions -> run ledger -> evals -> promotion
```

The ledger viewer makes that loop inspectable. It lets a user answer:

- What did the system plan?
- Which adapter produced evidence?
- Did evals pass, fail, or block promotion?
- Which action should I inspect next?

This is also a future product surface. A hosted dashboard can start from the
same ledger view instead of inventing a separate data model too early.
