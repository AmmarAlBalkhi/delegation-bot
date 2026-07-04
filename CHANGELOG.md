# Changelog

All notable changes to Delegation Bot will be documented here.

The project is currently pre-release.

## 0.1.0a0 - Unreleased

- Added Harnessfile validation.
- Added dry-run plan compilation and JSONL run ledgers.
- Added agent passports, capability packs, evals, and promotion reports.
- Added adapter contracts and an adapter contract CLI.
- Added Anthropic Claude and Claude Code planning contracts.
- Added adapter SDK primitives and a dry-run `github.issue` adapter.
- Added a no-network `sample.echo` adapter and adapter author guide.
- Added a `delegation ledger` viewer for JSONL run evidence.
- Added compact ledger fixtures for good, blocked, and failed adapter results.
- Added a `required_adapter_evidence` eval for SDK-backed adapter results.
- Improved the README with a 60-second dry-run demo.
- Added starter playbooks for code review, CI repair, and documentation refresh.
- Added GitHub Action artifact upload for run evidence.
- Added SDK-backed dry-run adapters for `mcp.tool`, `openai.agents`,
  `anthropic.messages`, and `claude.code`.
- Added an adapter fixture generator for good, blocked, and failed ledgers.
- Added eval-to-issue feedback loop design notes.
- Added playbook catalog metadata and validation.
- Added SDK-backed dry-run adapters for `github.actions`, `codex.thread`, and
  `local.classifier`.
- Added `delegation feedback` for dry-run GitHub Issue drafts from eval
  evidence.
- Added `delegation catalog` for playbook catalog summaries and JSON output.
- Added package metadata for source installs and the `delegation` console
  command.
- Added the `delegation_bot` package namespace with compatibility wrappers for
  existing `scripts/*.py` commands.
- Switched the project license and package metadata to Apache-2.0 with a
  project `NOTICE` file.
- Hardened GitHub Actions evidence artifacts with generated adapter fixtures,
  QA logs, license files, and release metadata.
- Added SDK-backed dry-run adapters for `langgraph.graph`, `human.approval`,
  `openclaw.gateway`, and `hermes.agent`.
- Added repeat grouping and create/update metadata for eval-to-issue feedback
  drafts.
- Added OpenTelemetry mapping notes for ledger events, adapters, evals, and
  future exporter work.
- Added positioning notes for the product category, uniqueness argument, use
  cases, and future marketing language.
- Added release-readiness and weekly-planning playbooks with catalog metadata.
- Added adapter compatibility matrix and first live-execution gate design notes.
- Added a hybrid trust model that separates AI suggestions from deterministic
  verification, approval, ledger, eval, and promotion decisions.
- Added product-experience principles for low-friction onboarding, playbooks,
  AI-drafted Harnessfiles, helpful blocked states, and progressive disclosure.
- Moved original recurring task examples into
  `examples/legacy-recurring-tasks/` and labeled the old task bot as legacy
  compatibility so the repository presents the Harnessfile control plane first.
