# Delegation Bot

Delegation Bot is **mission control for agentic work**.

Write one Harnessfile, dry-run the plan, route work to adapters, inspect the
run ledger, run evals, and promote agents only when the evidence is good.

The big idea is a **harness for AI harnesses**: a repo-native layer above Codex,
Claude Code, Anthropic Claude, OpenAI Agents SDK, LangGraph, MCP tools, GitHub
Actions, local scripts, and human approval.

It should enable AI, not suppress it. Agents can earn more autonomy through
clear passports, capability packs, approval gates, ledger evidence, evals, and
promotion rules.

The trust model is hybrid:

```text
AI proposes.
Delegation Bot verifies.
Human approves risky actions.
Ledger records everything.
Evals decide whether trust increases.
```

The experience should stay low-friction: useful in 60 seconds, powerful after
10 minutes, and deep only when the user asks for depth.

## 60-Second Demo

Clone the repo and run the dry-run control-plane loop:

```bash
python -m pip install -r requirements.txt
python scripts/delegation.py doctor --skip-github
python scripts/delegation.py suggest "prepare this repo for release" --output .delegation/suggested-release.yaml --plan --ledger .delegation/suggested-release.jsonl
python scripts/delegation.py plan examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl
python scripts/delegation.py ledger .delegation/latest.jsonl --adapter sample.echo
python scripts/delegation.py eval examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl --write
python scripts/delegation.py promote examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl
python scripts/delegation.py otel .delegation/latest.jsonl --output .delegation/latest-otel.json
python scripts/delegation.py apply-issues examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl
```

What you get:

- a readable execution plan before any live action
- a JSONL run ledger with adapter evidence
- a local OpenTelemetry-style JSON export for dashboards and later tracing
- `github.issue` and no-network `sample.echo` adapter results
- evals for duplicate issue markers, risky approvals, required adapter evidence,
  and pull-request readiness
- a promotion report showing which agents are still blocked

After dependencies are installed, the Delegation Bot demo does not require a
GitHub write, model call, network call, or agent execution. It is safe by
default.

Try the compact ledger fixtures:

```bash
python scripts/delegation.py ledger examples/ledgers/adapter-good.jsonl --adapter sample.echo
python scripts/delegation.py ledger examples/ledgers/adapter-blocked.jsonl --status blocked
python scripts/delegation.py ledger examples/ledgers/adapter-failed.jsonl --status failed
```

Those three files show good, blocked, and failed adapter evidence in the
smallest possible form.

## Features

- Harnessfile planning for models, agent passports, capability packs, policies,
  outputs, evals, and run ledgers
- `delegation doctor` for local readiness checks and a clear next command
- `delegation suggest` for no-blank-page Harnessfile drafts from plain-language
  goals
- opt-in live model-backed `delegation suggest` for OpenAI and Anthropic,
  gated by `--allow-live-model`
- `delegation apply-issues` for preview-first, live-gated `github.issue` writes
- `delegation otel` for local OpenTelemetry-style trace/log JSON exports
- no-network model-backed suggestion fixtures for OpenAI and Anthropic paths
- Adapter contracts for AI harnesses, workflows, tools, ML steps, and human
  approvals
- Adapter SDK with dry-run adapters for `github.issue`, `github.actions`,
  `codex.thread`, `openai.agents`, `anthropic.messages`, `claude.code`,
  `mcp.tool`, `langgraph.graph`, `human.approval`, `openclaw.gateway`,
  `hermes.agent`, `local.classifier`, and no-network `sample.echo`
- Ledger viewer for adapter evidence, eval results, and recent run events
- Adapter fixture generator for good, blocked, and failed SDK-backed ledgers
- Feedback issue drafts from failed or blocked eval evidence
- Built-in evals for ledger validity, approvals, duplicate markers, required
  adapter evidence, and pull-request test evidence
- Starter playbooks for code review, CI repair, and documentation refresh, plus
  catalog metadata for tags, adapters, and expected dry-run eval states
- Legacy recurring GitHub Issue bot retained for existing `tasks/*.md` users

## Big Direction

The long-term product is not just issue creation. It is an AI operations harness
that can coordinate many underlying harnesses:

- OpenAI Agents SDK, Anthropic Claude, Claude Code, LangGraph, custom scripts,
  GitHub Actions, MCP servers, and human review steps
- durable run ledgers with evidence, artifacts, decisions, approvals, and cost
- policy gates for permissions, secrets, budgets, tool risk, and human signoff
- agent passports and capability packs that let AI earn more autonomy over time
- evals that turn every run into regression data
- adapters that let teams switch agent frameworks without rewriting delegation
  plans

See [docs/vision.md](docs/vision.md), [docs/architecture.md](docs/architecture.md),
[docs/positioning.md](docs/positioning.md),
[docs/agent-enablement.md](docs/agent-enablement.md),
[docs/hybrid-trust-model.md](docs/hybrid-trust-model.md),
[docs/product-experience.md](docs/product-experience.md), and
[docs/adapter-contracts.md](docs/adapter-contracts.md) for the strategic
blueprint. See [docs/adapter-sdk.md](docs/adapter-sdk.md) for the plug-in
standard that adapter implementations must satisfy,
[docs/build-an-adapter.md](docs/build-an-adapter.md) for the contributor path,
[docs/adapter-compatibility.md](docs/adapter-compatibility.md) for current
adapter status, [docs/live-execution-gate.md](docs/live-execution-gate.md) for
the first safe live-execution design, [docs/doctor.md](docs/doctor.md) for
local readiness checks,
[docs/github-issue-apply.md](docs/github-issue-apply.md) for the first live
gated GitHub Issue path,
[docs/github-app-installation.md](docs/github-app-installation.md) for the
future scoped GitHub App path,
[docs/harnessfile-suggest.md](docs/harnessfile-suggest.md) for the
no-blank-page suggestion flow,
[docs/model-backed-suggest.md](docs/model-backed-suggest.md) for the explicit
opt-in model-backed suggestion design and no-network fixtures,
[docs/ledger-viewer.md](docs/ledger-viewer.md) for inspecting run evidence,
[docs/ledger-fixtures.md](docs/ledger-fixtures.md) for compact good, blocked,
and failed examples, [docs/playbooks.md](docs/playbooks.md) for reusable
Harnessfile missions, [docs/eval-to-issue-feedback.md](docs/eval-to-issue-feedback.md)
for the improvement loop, [docs/opentelemetry-mapping.md](docs/opentelemetry-mapping.md)
for observability mapping and the local exporter,
[docs/dashboard-wireframe.md](docs/dashboard-wireframe.md) for the future
hosted cockpit, and [ROADMAP.md](ROADMAP.md) for the million-star plan.

For public launch planning, see [CONTRIBUTING.md](CONTRIBUTING.md),
[SECURITY.md](SECURITY.md), [docs/contributor-license-policy.md](docs/contributor-license-policy.md),
and [docs/domain-strategy.md](docs/domain-strategy.md). For public contribution
triage, see [docs/public-roadmap-issues.md](docs/public-roadmap-issues.md) and
[docs/issue-labels.md](docs/issue-labels.md).
For business assumptions and the active work queue, see
[docs/business-model.md](docs/business-model.md) and
[docs/next-actions.md](docs/next-actions.md). For package release rehearsal,
see [docs/testpypi-dry-run.md](docs/testpypi-dry-run.md).

## Current Status

Today the project has two layers:

- **Harness control plane:** Harnessfiles can validate, compile into dry-run
  plans, emit ledgers, expose adapter evidence, run evals, and evaluate agent
  promotion readiness.
- **Legacy task bot:** The original Markdown recurring issue bot is retained
  for compatibility, but it is no longer the main product path.

Live agent execution is intentionally not enabled yet. The current focus is
trustworthy dry-runs, adapter contracts, evidence, and contributor-friendly
examples.

## Legacy Recurring Issue Bot

The original proof of concept can still dry-run or create recurring GitHub
Issues from Markdown task specs. It is useful for migration and simple personal
automation, but new users should start with Harnessfiles and playbooks.

Retained examples live in
`examples/legacy-recurring-tasks/`.

The legacy script still defaults to `tasks/*.md` for existing users. To run the
retained examples directly, set `TASK_GLOB`.

Legacy Markdown files use YAML front matter:

```yaml
---
id: weekly-status
repository: owner/repo
title: Weekly Status Pack
assign: [octocat]
labels: [delegation, recurring, weekly]
date_active: 2026-01-01
due_in_days: 7
interval: weekly
project:
  title: Delegation Bot
subtasks:
  - id: collect-notes
    title: Collect weekly notes
  - id: send-summary
    title: Send summary
---

Write any issue body content here.
```

Required fields:

- `id`: stable identifier for idempotency
- `title`: issue title
- `repository`: `owner/repo`, unless `REPO` or `GITHUB_REPOSITORY` is set

Useful optional fields:

- `assign`: one login or a list of logins
- `labels`: one label or a list of labels
- `date_active` or `start`: do not create the task before this date
- `due_date`, `due`, or `due_in_days`
- `interval`: `once`, `daily`, `weekly`, `monthly`, or `every:N`
- `project`: either a project title string or an object with `title`
- `subtasks`: child issue specs with `id` and `title`

Legacy scheduling rules:

- `once` creates one issue for the task family.
- `daily` creates one issue per UTC date.
- `weekly` creates one issue per ISO week.
- `monthly` creates one issue per calendar month.
- `every:N` runs every N days, anchored to `start` or `date_active`.
- Future `date_active` or `start` values are skipped until that date arrives.

The bot is safe to re-run. It searches existing issue bodies for hidden markers
before creating new Issues.

## GitHub Action

The included workflow lives at `.github/workflows/delegation.yml`.

It now serves two purposes:

- run the legacy issue bot only when legacy task specs are present or
  `TASK_GLOB` is configured
- always generate Harnessfile dry-run evidence and upload ledger, report,
  fixture, and OpenTelemetry export artifacts

To inspect generated evidence after a workflow run:

1. Open the workflow run in GitHub Actions.
2. Download the `delegation-run-evidence` artifact.
3. Inspect `.delegation/harness-dry-run.jsonl`,
   `.delegation/harness-ledger-report.txt`,
   `.delegation/harness-otel.json`, and `.delegation/fixtures/`.

`GITHUB_TOKEN` is provided automatically by GitHub Actions. Set `PROJECT_TOKEN`
only if your Project v2 access requires a separate fine-grained token.

## Local Development

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Install from source with the package command:

```bash
python -m pip install -e .
delegation --help
```

The installable Python package namespace is `delegation_bot`. The older
`scripts/*.py` commands remain as compatibility wrappers while the project moves
toward normal packaging.

Run tests:

```bash
python -m unittest discover -s tests -v
```

Run the full local QA suite:

```bash
python scripts/qa.py
```

Validate an AI harness manifest:

```bash
python scripts/delegation.py validate examples/ai-harness-control-plane.yaml
```

After installing from source, the same command is available as:

```bash
delegation validate examples/ai-harness-control-plane.yaml
```

You can also run the package module directly:

```bash
python -m delegation_bot adapters codex.thread
```

Compile a dry-run plan:

```bash
python scripts/delegation.py plan examples/ai-harness-control-plane.yaml
```

Draft a Harnessfile from a plain-language goal:

```bash
python scripts/delegation.py suggest "prepare this repo for release" --output .delegation/suggested-release.yaml --plan --ledger .delegation/suggested-release.jsonl
```

Try no-network model-backed suggestion fixtures:

```bash
python scripts/delegation.py suggest "prepare this repo for release" --draft-source fixture --provider openai --output .delegation/model-openai-release.yaml --plan --ledger .delegation/model-openai-release.jsonl
python scripts/delegation.py suggest "review this pull request" --draft-source fixture --provider anthropic --output .delegation/model-anthropic-review.yaml --plan --ledger .delegation/model-anthropic-review.jsonl
```

Run an explicit live model-backed suggestion only when you want a provider API
call:

```bash
OPENAI_API_KEY=sk_your_key python scripts/delegation.py suggest "prepare this repo for release" --draft-source model --provider openai --allow-live-model --output .delegation/model-openai-release.yaml --plan --ledger .delegation/model-openai-release.jsonl
ANTHROPIC_API_KEY=sk-ant-your_key python scripts/delegation.py suggest "review this pull request" --draft-source model --provider anthropic --allow-live-model --output .delegation/model-anthropic-review.yaml --plan --ledger .delegation/model-anthropic-review.jsonl
```

Live suggestions only draft Harnessfiles. Delegation Bot still validates,
dry-runs, writes ledgers, runs evals, and requires human approval for risky
actions.

List built-in adapter contracts:

```bash
python scripts/delegation.py adapters
```

Inspect one adapter contract:

```bash
python scripts/delegation.py adapters codex.thread --json
```

Write a dry-run run ledger:

```bash
python scripts/delegation.py plan examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl
```

Run built-in evals and append eval evidence:

```bash
python scripts/delegation.py eval examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl --write
```

Draft improvement issues directly from the eval results:

```bash
python scripts/delegation.py eval examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl --feedback --feedback-include-blocked
```

Preview the live GitHub Issue apply gate:

```bash
python scripts/delegation.py apply-issues examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl
```

Draft dry-run feedback issues from failed or blocked eval evidence:

```bash
python scripts/delegation.py feedback examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl --include-blocked
```

Inspect the run ledger:

```bash
python scripts/delegation.py ledger .delegation/latest.jsonl --adapter github.issue
```

Export the ledger to local OpenTelemetry-style JSON:

```bash
python scripts/delegation.py otel .delegation/latest.jsonl --output .delegation/latest-otel.json
```

Inspect the no-network sample adapter:

```bash
python scripts/delegation.py ledger .delegation/latest.jsonl --adapter sample.echo
```

Inspect a compact fixture:

```bash
python scripts/delegation.py ledger examples/ledgers/adapter-good.jsonl --adapter sample.echo
python scripts/delegation.py ledger examples/ledgers/github-issue-applied.jsonl --adapter github.issue
```

Try a starter playbook:

```bash
python scripts/delegation.py plan playbooks/code-review.yaml --ledger .delegation/playbook-code-review.jsonl
python scripts/delegation.py eval playbooks/code-review.yaml --ledger .delegation/playbook-code-review.jsonl --write
```

Try the flagship release-readiness playbook:

```bash
python scripts/delegation.py plan playbooks/release-readiness.yaml --ledger .delegation/playbook-release-readiness.jsonl
python scripts/delegation.py eval playbooks/release-readiness.yaml --ledger .delegation/playbook-release-readiness.jsonl --write
python scripts/delegation.py promote playbooks/release-readiness.yaml --ledger .delegation/playbook-release-readiness.jsonl
```

Browse starter playbook metadata in `playbooks/catalog.yaml`.

Summarize the playbook catalog:

```bash
python scripts/delegation.py catalog
```

Filter the playbook catalog:

```bash
python scripts/delegation.py catalog --tag release
python scripts/delegation.py catalog --adapter github.actions
python scripts/delegation.py catalog --tag ci --adapter github.actions
python scripts/delegation.py catalog --list-tags --list-adapters
```

Evaluate whether agents are ready for promotion:

```bash
python scripts/delegation.py promote examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl
```

Create a timestamped source backup:

```bash
python scripts/backup_repo.py
```

Generate an adapter fixture:

```bash
python scripts/generate_adapter_fixtures.py mcp.tool --state good --output .delegation/adapter-mcp-tool-good.jsonl
```

See [docs/qa.md](docs/qa.md) for the backup, QA, type, and documentation
discipline.

## Packaging And License

Delegation Bot is preparing for other users through `pyproject.toml` and the
installable `delegation` CLI command. See [docs/release.md](docs/release.md)
for the release checklist.

The project uses the Apache License 2.0. The short version: the core stays open
and business-friendly, while the project gets clearer patent protection,
contribution terms, and attribution through `NOTICE`. See
[docs/license-strategy.md](docs/license-strategy.md) for the decision notes.

The license does not block future paid hosted services, private adapters,
support, or enterprise controls. Those assumptions live in
[docs/business-model.md](docs/business-model.md).

Run the bot locally in dry-run mode:

```bash
GITHUB_TOKEN=ghp_your_token REPO=owner/repo python scripts/delegation_bot.py
```

Run the retained legacy examples:

```bash
TASK_GLOB=examples/legacy-recurring-tasks/*.md GITHUB_TOKEN=ghp_your_token REPO=owner/repo python scripts/delegation_bot.py
```

Run in apply mode only when you are ready to create or update Issues:

```bash
APPLY=true GITHUB_TOKEN=ghp_your_token REPO=owner/repo python scripts/delegation_bot.py
```
