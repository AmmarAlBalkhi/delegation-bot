# QA And Backup Discipline

This project should be built with evidence, not hope. Every meaningful change
should leave behind a small trail: what was changed, how it was checked, and how
to recover if the direction was wrong.

## Default Workflow

1. Create a backup before a substantial edit.
2. Make the smallest coherent change.
3. Run the local QA command.
4. Document any new behavior, policy, or architectural decision.
5. Create another backup after a stable milestone.

## Backup Command

Create a timestamped zip backup outside the repository:

```bash
python scripts/backup_repo.py
```

Preview the target backup path without writing:

```bash
python scripts/backup_repo.py --dry-run
```

Backups default to `../backups/` relative to the repository. They exclude git
metadata, bytecode caches, virtual environments, and common local tool caches.

## QA Command

Run the standard local check suite:

```bash
python scripts/qa.py
```

The QA command currently checks:

- Python bytecode compilation for `scripts/` and `tests/`
- unit tests
- package metadata parsing
- package module CLI smoke test
- CLI version smoke test
- release-readiness report smoke test
- release rehearsal evidence bundle generation
- app-ready state bundle generation for the future local cockpit
- installed package control-loop demo, mission-status, agent-packet, and
  app-state smoke tests
- installed package Agent Passport smoke test
- first-run `delegation demo` and `delegation init` flows
- example Harnessfile validation
- example Harnessfile dry-run planning
- local OpenTelemetry export generation
- adapter contract listing and inspection
- adapter fixture generation
- no-network model-backed suggestion fixtures
- mocked live model-backed suggestion provider tests
- mocked Ollama-backed local model suggestion tests
- release artifact workflow checks for ledgers, fixtures, QA logs, `LICENSE`,
  and `NOTICE`
- built-in eval generation from the generated QA ledger
- direct eval-result feedback issue draft generation
- feedback issue draft generation from eval evidence
- feedback issue memory fixture coverage
- feedback recovery fixture coverage
- dashboard snapshot generation from fixture ledgers
- Agent Passport registry generation from Harnessfiles and custom BYOA
  registry files
- control-loop demo coverage for Agent Gate, local approval, RunPrint ingest,
  and audit receipts
- mission-status coverage for plain ledger state over the control loop
- agent-packet coverage for Bring Your Own Agent handoff JSON
- GitHub Actions dispatch preview, gated fake-client live path, and fixture coverage
- GitHub Actions live preflight, duplicate-run blocking, and cancellation
  evidence coverage
- GitHub App permission and scoped installation-token planning
- GitHub Actions dispatch idempotency and secret-safe dispatch fingerprints
- GitHub Actions cancel preview, token diagnostics, and fake-client cancellation
  evidence coverage
- MCP tool risk evidence eval and fixture coverage
- MCP tool policy gate coverage
- local-classifier policy profile evidence
- deterministic and mocked Ollama policy explanation coverage
- optional Windows EXE packaging dependency metadata
- Windows EXE build script structure, user-local install script structure, and
  generated artifact ignores
- release artifact checksum and manifest generation, including stale checksum
  detection
- read-only CLI behavior without eager live-network imports
- example promotion report from the generated QA ledger
- starter playbook validation and dry-run planning
- playbook catalog CLI summary
- playbook catalog tag and adapter filtering
- playbook catalog validation through unit tests
- GitHub issue templates and label metadata through unit tests
- live model suggest API gate and parsing through unit tests
- JSON parsing for schema files

## Type Discipline

Python code should use explicit type annotations for public functions and
helpers that cross module boundaries. For flexible manifest data, use named type
aliases so the intent is visible even when the underlying value is dynamic.

When the project grows, the next step is adding a static type checker in CI.
Until then, keep runtime validation close to manifest boundaries and cover
schema behavior with tests.

## Packaging Discipline

Package metadata must stay aligned with the actual project state:

- `pyproject.toml` license must match the Apache-2.0 `LICENSE`
- `NOTICE` must identify the project attribution notice
- the package distribution name is `delegationhq`
- dependency constraints should match runtime imports
- the `delegation` console command should point at the CLI entry point
- `python -m delegation_bot` should work as a package module entry point
- alpha versions should be used until public schemas are stable

Before a public release, run the checklist in `docs/release.md`.
Use `delegation release-check` for a quick local release-readiness report, and
`delegation release-check --strict-artifacts` after standalone artifacts are
built.

## Documentation Expectations

Document each durable project decision in `docs/decision-log.md`.

Documentation should answer:

- what changed
- why it exists
- how to verify it
- what future work it unlocks

## Evidence Standard

A task is not complete because the agent says it is complete. It is complete
when the required checks, docs, artifacts, or links exist and can be inspected.
