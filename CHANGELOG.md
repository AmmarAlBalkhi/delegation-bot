# Changelog

All notable changes to DelegationHQ will be documented here.

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
- Added `delegation app-plan` for the first Windows EXE mission-cockpit plan
  with Bring Your Own Agent passport direction.
- Added Agent Gate ledger receipts and `delegation agent-audit` for comparing
  approved intent with planned or recorded RunPrint evidence.
- Added `delegation approval-inbox` and `delegation approval-decision` for
  local human approve/block receipts over Agent Gate cards.
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
- Added MCP tool permission scope, risk-level, prompt-injection risk evidence,
  a `mcp_tool_risk_review` eval, and a high-risk MCP fixture.
- Added `delegation mcp-gate` for MCP server/tool allowlist and risk gate
  reports, plus a 60-second demo guide and Windows EXE packaging plan.
- Added `delegation demo`, `delegation init`, and an installed-package demo
  smoke test to make first-run setup faster and more production-like.
- Added `delegation agent-gate` for Agent Passport action previews across
  Harnessfile agents and custom registries, with JSON output for `app-state`.
- Added opt-in Ollama-backed `delegation suggest` so local models can draft
  Harnessfiles through the same validation and dry-run ledger path.
- Added a Windows `.exe` build script with bundled runtime assets and safe
  demo/init/validate smoke checks.
- Added deterministic local-classifier policy profiles with recommended gate
  evidence.
- Added gated live `delegation apply-actions` dispatch with exact confirmation,
  token checks, input-count gates, and dispatch ledger events.
- Hardened live GitHub Actions dispatch with workflow metadata preflight,
  duplicate active-run protection, dispatch-time rechecks, and cancellation
  guidance in ledger evidence.
- Added `delegation explain-policy` for deterministic and opt-in Ollama-backed
  explanations of classifier evidence without granting model authority.
- Made read-only CLI commands avoid importing live network dependencies until
  a live apply or live model call needs them.
- Added a researched adapter candidate matrix for prioritizing real-world
  harness integrations.
- Added `delegation dashboard` for read-only mission snapshots from ledger
  evidence.
- Added `delegation recover-feedback` for recovery drafts when previously
  failing evals pass after a live feedback issue exists.
- Added a feedback recovery ledger fixture.
- Moved the public package identity from `delegation-bot` to `delegationhq`
  while preserving the `delegation` CLI and `delegation_bot` Python namespace.
- Added a user-local Windows installer for `delegation.exe`.
- Added `delegation --version`, version smoke checks, and clearer doctor next
  steps for the first-run path.
- Added `delegation release-check` for local alpha release-readiness reports
  across package metadata, docs, legal files, QA evidence, Windows packaging,
  git state, and standalone artifacts.
- Added `delegation github-app-plan` for local GitHub App permission and scoped
  installation-token planning across read-only, issue-write, and
  actions-control modes.
- Added `delegation cancel-actions` for preview-first GitHub Actions
  cancellation, with exact confirmation, force-cancel gating, token
  diagnostics, optional ledger evidence, and fake-client coverage.
- Added secret-safe GitHub Actions dispatch ids and a ledger idempotency gate
  that blocks repeated live dispatches for the same workflow/ref/input shape.
- Added `delegation artifacts` for release artifact checksums and a structured
  artifact manifest, and wired checksum verification into the Windows EXE build
  path.
- Added `delegation release-rehearse` for local release evidence bundles that
  collect release readiness, artifact verification, git state, metadata, and
  next steps without publishing anything.
- Added `delegation app-state` as one read-only state bundle for the future
  local cockpit, combining app plan, doctor, release readiness, mission
  snapshot, evidence bundles, next action, and guardrails.
- Added `delegation agents` for Agent Passport registry reports across
  Harnessfile agents and custom Bring Your Own Agent registry files.
