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
- Added `delegation suggest` to draft valid Harnessfiles from plain-language
  goals using no-network templates, with optional dry-run planning and ledger
  output.
- Added opt-in model-backed `delegation suggest` design notes, a structured
  draft schema, and blocked-eval repeat thresholds for lower-noise feedback.
- Added `delegation doctor` for local readiness checks and first-run guidance.
- Added preview-first `delegation apply-issues` with explicit live gates for
  `github.issue` writes.
- Clarified that star milestones are aspirational target states, not traction
  claims.
- Added `delegation otel` for local OpenTelemetry-style JSON export from
  ledgers.
- Added no-network model-backed suggestion fixtures for OpenAI and Anthropic.
- Added an applied `github.issue` ledger fixture.
- Added TestPyPI dry-run release notes.
- Added direct `EvalResult` to feedback issue draft conversion through
  `delegation eval --feedback`.
- Added playbook catalog filtering by tag and adapter.
- Added hosted dashboard wireframe notes.
- Added contributor license and DCO policy notes.
- Added public roadmap issue drafts, issue label source of truth, and
  good-first-issue curation notes.
- Added GitHub App installation design notes.
- Improved issue templates for adapters, evals, playbooks, bugs, and design
  proposals.
- Added opt-in live model-backed `delegation suggest` for OpenAI and Anthropic.
- Kept live model calls behind `--allow-live-model`, API-key checks, draft
  envelope validation, Harnessfile validation, and dry-run planning.
- Made default `delegation suggest` output shorter so full YAML appears only
  with `--yaml` or `--output`.
- Linked eval feedback update drafts to live GitHub issue numbers and URLs so
  repeated failures reuse existing issues.
- Added a feedback issue memory ledger fixture and duplicate-marker handling for
  intentional feedback update lifecycles.
- Added `delegation apply-actions` as a preview-first GitHub Actions dispatch
  gate with run URL evidence, fixture coverage, and docs.
- Made read-only CLI commands avoid importing live network dependencies until
  a live apply or live model call needs them.
- Added a researched adapter candidate matrix for prioritizing real-world
  harness integrations.
- Added `delegation dashboard` for read-only mission snapshots from ledger
  evidence.
- Added `delegation recover-feedback` for recovery drafts when previously
  failing evals pass after a live feedback issue exists.
- Added a feedback recovery ledger fixture.
