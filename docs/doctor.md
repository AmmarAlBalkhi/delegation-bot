# Delegation Doctor

`delegation doctor` checks whether the local control-plane loop is ready.

Caveman version:

```text
Bot check itself.
Bot say ready or not ready.
Bot give next step.
```

## Why It Exists

DelegationHQ should feel powerful, not confusing. Before live GitHub writes,
model-backed suggestions, hosted dashboards, or release packaging, users need a
simple way to answer:

```text
Is my setup ready?
What is broken?
What should I do next?
```

## Usage

```bash
delegation doctor
```

For deterministic local or CI checks without GitHub auth probing:

```bash
delegation doctor --skip-github
```

For tools:

```bash
delegation doctor --json
```

## Checks

The doctor currently checks:

- Python version
- required Python dependencies
- package metadata
- Apache-2.0 license and `NOTICE`
- JSON schemas
- flagship example Harnessfile validation
- `delegation suggest` -> dry-run plan -> ledger loop
- compact ledger fixtures
- Git worktree status
- GitHub CLI/auth readiness when not skipped

GitHub CLI problems are warnings, not failures. They matter for future live
apply mode, but they should not block safe dry-runs.

## Product Rule

Doctor should reduce anxiety.

It should not:

- make network writes
- call models
- create GitHub Issues
- require GitHub auth for dry-run use
- dump walls of JSON unless `--json` is requested

It should:

- summarize what is ready
- explain what needs attention
- give a useful next command
