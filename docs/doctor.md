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

For local GitHub App setup diagnostics:

```bash
delegation doctor --github-app
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
- optional GitHub App auth readiness with `--github-app`

GitHub CLI and GitHub App auth problems are warnings, not failures. They matter
for future live apply mode, but they should not block safe dry-runs.

`delegation doctor --github-app` does not mint a token, call GitHub, create an
issue, or print secrets. It checks only local setup:

- required GitHub App env vars are present
- private key path is readable, if a path is used
- optional signing dependencies are installed
- token minting is still left to explicit live apply commands

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
- show a safe fast path first: `delegation demo`
- give clear optional setup steps only when they matter

The first successful output should feel like:

```text
Status: ready
Next:
- delegation demo
- delegation init --goal "prepare this repo for safe AI delegation"
```
