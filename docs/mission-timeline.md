# Mission Timeline

`timeline` turns a JSONL ledger into an ordered control-loop history.

```bash
delegation timeline --workspace .
delegation timeline --ledger .delegation/agent-run.jsonl --json
```

It groups events into stages:

- `plan`
- `gate`
- `approval`
- `execute`
- `record`
- `eval`
- `feedback`
- `promote`

Simple version:

```text
What happened?
Who asked?
Who approved?
Did it run?
Did RunPrint record proof?
What needs attention?
```

## Why It Matters

DelegationHQ should not feel like scattered commands. A user needs one proof
trail that explains the mission in order.

The timeline is also app-ready JSON. A future interface can render it as a
mission history without reimplementing ledger parsing.

## Boundary

This command is read-only. It explains ledger evidence but does not run agents,
approve requests, or change files.
