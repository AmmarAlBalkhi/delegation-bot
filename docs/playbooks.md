# Playbooks

Playbooks are reusable Harnessfiles for common agentic workflows.

Think of them as starter missions. A user copies one, changes the repository,
owners, allowed files, and model names, then runs the same dry-run loop:

```bash
python scripts/delegation.py validate playbooks/code-review.yaml
python scripts/delegation.py plan playbooks/code-review.yaml --ledger .delegation/playbook-code-review.jsonl
python scripts/delegation.py ledger .delegation/playbook-code-review.jsonl --adapter sample.echo
python scripts/delegation.py eval playbooks/code-review.yaml --ledger .delegation/playbook-code-review.jsonl --write
python scripts/delegation.py promote playbooks/code-review.yaml --ledger .delegation/playbook-code-review.jsonl
```

The current playbooks are dry-run first. They do not call models, write to
GitHub, run workflows, or execute agents. They produce a readable plan and run
ledger so users can inspect the mission before any live action exists.

## Starter Playbooks

The catalog lives at `playbooks/catalog.yaml`. It adds tags, required adapters,
and expected dry-run eval states for each starter playbook.

Use it as the future marketplace index: a UI, GitHub Action, or docs generator
can read one file and understand which playbook fits a job.

Inspect the catalog from the CLI:

```bash
python scripts/delegation.py catalog
```

### `playbooks/code-review.yaml`

Use this when a change needs an AI-assisted review plus human signoff.

It plans:

- a GitHub Issue for review scope and findings
- a no-network `sample.echo` evidence receipt
- a Claude Code review handoff
- a human approval checkpoint
- evals for duplicate issue markers, risky approvals, and adapter evidence

### `playbooks/ci-repair.yaml`

Use this when CI fails and the team needs a small, auditable repair loop.

It plans:

- a GitHub Issue for the failing workflow and repair checklist
- a no-network `sample.echo` evidence receipt
- a local risk-classifier step
- a Codex thread handoff for the repair
- a GitHub Actions verification step
- evals for adapter evidence, approvals, and tests before PR readiness

The `tests_pass_before_pr` eval may stay blocked in a pure dry-run. That is
intentional: a real repair should not be promoted until actual test evidence
exists in the ledger.

### `playbooks/documentation-refresh.yaml`

Use this when docs need to be brought back in sync with implemented behavior.

It plans:

- a GitHub Issue for the documentation refresh scope
- a no-network `sample.echo` evidence receipt
- a Codex thread handoff for scoped docs changes
- a human approval checkpoint
- evals for duplicate issue markers, risky approvals, and adapter evidence

### `playbooks/release-readiness.yaml`

Use this as the flagship demo when a project needs to prove it is ready to
release.

It plans:

- a GitHub Issue for release scope, blockers, and evidence
- a no-network `sample.echo` evidence receipt
- a local risk-classifier step
- a Codex thread handoff for scoped release doc or metadata fixes
- a GitHub Actions verification step
- a human approval checkpoint
- evals for adapter evidence, approvals, duplicates, and test evidence before
  pull request readiness

The `tests_pass_before_pr` eval may stay blocked in a pure dry-run. That is the
point: release promotion should wait for real test evidence.

### `playbooks/weekly-planning.yaml`

Use this when a team wants a repeatable weekly planning loop with AI help but
human control.

It plans:

- a GitHub Issue for weekly priorities, owners, blockers, and decisions
- a no-network `sample.echo` evidence receipt
- an OpenAI Agents SDK-style planning handoff
- a human approval checkpoint
- evals for duplicate issue markers, risky approvals, and adapter evidence

## Playbook Standard

A good playbook should include:

- a clear objective
- accountable owners
- catalog metadata in `playbooks/catalog.yaml`
- models and agents, even if execution is still dry-run only
- capability packs that explain what each agent may do
- at least one `github.issue` executor so the plan has a visible coordination surface
- at least one no-network `sample.echo` executor so adapter evidence can be tested locally
- policies for approvals, budget, permissions, and network scope
- `run_ledger` and `eval_report` outputs
- `required_adapter_evidence` in evals

Keep playbooks boring on purpose. Their power comes from repeatability: copy,
customize, dry-run, inspect the ledger, then decide whether the mission deserves
more autonomy.
