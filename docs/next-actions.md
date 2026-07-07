# Next Actions

This is the active work queue. Keep it short so the project does not drift.

## Core Idea

DelegationHQ is a harness for AI harnesses:

```text
Harnessfile -> dry-run plan -> policy gates -> adapter actions -> run ledger -> evals -> promotion
```

Everything should strengthen that loop.

The trust model is hybrid:

```text
AI proposes.
DelegationHQ verifies.
Human approves risky actions.
Ledger records everything.
Evals decide whether trust increases.
```

The experience rule is:

```text
Useful in 60 seconds.
Powerful after 10 minutes.
Deep only when the user asks for depth.
```

## Now

1. Run `delegation release-check --strict-artifacts` on a clean Windows release
   host after building the `.exe` and checksum file.
2. Open the first small public roadmap issue set from
   `docs/public-roadmap-issues.md` when maintainers are ready.
3. Decide which `delegation github-app-plan` mode should become the first
   hosted GitHub App implementation target.
4. Add GitHub App auth diagnostics to `delegation doctor`.
5. Decide whether a dedicated `github.actions` cancel command belongs in the
   next public batch.

## Completed Recently

- Hardened `github.actions` live dispatch with workflow metadata preflight,
  active duplicate-run protection, dispatch-time rechecks, cancellation guidance
  in ledger evidence, and focused fake-client tests.
- Added `delegation release-check` for local alpha release-readiness reports
  that do not publish, tag, or call external services.
- Added `delegation github-app-plan` for local GitHub App permission and
  scoped installation-token planning before live app auth exists.
- Added `delegation apply-feedback` for gated feedback recovery comments and
  optional issue closing with separate confirmation tokens.
- Added the first GitHub App issue-write auth boundary for live issue commands
  through `--auth github-app`.
- Added `delegation --version`, package/EXE version smoke checks, and clearer
  doctor next steps that start with `delegation demo`.
- Moved the public/package identity to DelegationHQ while preserving the
  `delegation` CLI and `delegation_bot` Python namespace.
- Added a user-local Windows installer for `delegation.exe` under
  `%LOCALAPPDATA%\DelegationHQ\bin`.
- Added gated live `github.actions` dispatch through `delegation apply-actions`
  with explicit confirmation, token gate, workflow input limits, dispatch ledger
  events, fake-client tests, and updated docs.
- Added `delegation explain-policy` so classifier evidence can be explained in
  plain language, with opt-in Ollama explanations that do not change gate
  authority.
- Added `delegation demo`, `delegation init`, and an installed-package smoke
  check so first-run users can see the product and create a Harnessfile quickly.
- Added opt-in Ollama-backed `delegation suggest` for local Harnessfile drafts
  that still pass through deterministic validation and dry-run ledgers.
- Added a Windows `.exe` build script with bundled runtime assets and safe
  demo/init/validate smoke checks.
- Added deterministic local-classifier policy profiles with recommended gate
  evidence.
- Added `delegation mcp-gate`, explicit MCP server/tool allowlist policy,
  a 60-second demo path, and a Windows EXE packaging plan.
- Added MCP tool permission scope, risk-level, prompt-injection risk evidence,
  `mcp_tool_risk_review`, a high-risk fixture, and docs.
- Added a `github.actions` dispatch preview gate with run URL evidence,
  approval policy checks, CLI coverage, fixture coverage, and docs.
- Added a researched real-world adapter candidate matrix.
- Added `delegation dashboard` as a read-only dashboard data model over ledger
  fixtures.
- Added `delegation recover-feedback` for evals that later pass after a live
  feedback issue exists.
- Added a feedback recovery ledger fixture.
- Linked eval feedback update drafts to live GitHub issue numbers and URLs.
- Added feedback issue memory fixture coverage.
- Allowed intentional feedback issue update lifecycles in the duplicate marker
  eval.
- Made read-only CLI imports avoid live network dependencies until needed.
- Added opt-in live model-backed `delegation suggest` for OpenAI and Anthropic.
- Added explicit `--allow-live-model` gating, API-key checks, model draft
  validation, and mocked provider tests.
- Made default `delegation suggest` output shorter and less boring.
- Added public roadmap issue drafts.
- Added issue label source of truth and good-first-issue curation notes.
- Added GitHub App installation design notes.
- Improved issue templates for adapters, evals, playbooks, bugs, and design
  proposals.
- Added hosted dashboard wireframe notes.
- Added Developer Certificate of Origin and contributor-license policy notes.
- Added playbook catalog filtering by tag and adapter.
- Added direct `EvalResult` to feedback issue draft conversion.
- Added the first local OpenTelemetry export command.
- Added fixture artifact download examples to README.
- Added TestPyPI dry-run release notes.
- Added no-network model-backed suggest fixtures for OpenAI and Anthropic.
- Added fixture coverage for applied `github.issue` ledger states.

## Later

1. Hosted dashboard prototype.
2. GitHub App installation flow.
3. Team approval workflows.
4. Slack, Linear, Jira, and enterprise adapters.
5. Public website or docs home when a domain is owned.
6. Trademark, hosted terms, and privacy-policy planning when needed.

## Parking Lot

These matter, but should not interrupt the core loop:

- domain purchase
- logo and visual identity
- long-form launch content

See `docs/open-core-strategy.md` for the public/private publishing boundary.
