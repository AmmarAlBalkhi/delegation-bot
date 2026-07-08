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

The simple mental model:

```text
Passport = agent ID card.
Agent Gate = guard at the door.
RunPrint = current camera/proof tool, not the whole product.
Evidence tools = future cameras, test reporters, monitors, logs, CRM recorders,
browser/session recorders, and business workflow proof collectors.
Evals = judges.
Human = final yes/no for danger.
```

## Now

1. Expand Bring Your Own Agent adapters from file-based handoff to live
   connector modes: CLI stdin/stdout, webhook callback, MCP tool call, and
   LangGraph invocation.
2. Improve the local app shell after visual direction is approved: agent list,
   approval cards, mission timeline, and evidence details should feel fast and
   obvious without exposing internal complexity.
3. Expand Agent Approval Preview with proposed file/resource diffs and command
   intent previews before risky writes.
4. Generalize evidence ingestion so RunPrint stays one recorder adapter among
   multiple future proof tools.
5. Keep `app-state` and `app-dashboard` aligned as cockpit backends without
   designing UI until the visual direction is approved.
6. Run `delegation release-check --strict-artifacts` on a clean Windows release
   host after building the `.exe`, checksum file, and artifact manifest.
7. Run `delegation release-rehearse --strict-artifacts` on a clean Windows host
   and keep the generated evidence bundle with release notes.
8. Test the GitHub App issue-write path against a real installed app before
   hosted auth work.
9. Decide which `delegation github-app-plan` mode should become the first
   hosted GitHub App implementation target.

## Completed Recently

- Added `delegation agent-result-ingest` so custom agents can return a result
  JSON that DelegationHQ validates against the Agent Packet before appending
  `agent.result.reported` and recorder evidence.
- Hardened `agent-packet` with an explicit Agent Result return contract,
  allowed statuses, ingest command, example payload, app rendering, smoke
  coverage, and a copyable handoff example.
- Expanded Approval Preview into a practical human control card with request
  packet context, resource scope, evidence status, repeated-action history,
  reviewer notes, expiration, app rendering, CLI flags, and regression tests.
- Turned the local app tester report into functional UX fixes: full timeline,
  copy buttons, labeled next actions, wrapped workspace paths, richer Agent
  Passport cards, local JSON links, refresh control, and regression coverage.
- Added `delegation app-dashboard` as the one-screen app brain: workspace
  state, Agent Passports, approval preview, command center, timeline, and next
  safe actions together.
- Added `delegation timeline` so a workspace ledger reads as plan -> gate ->
  approval -> execution -> recorded proof -> eval -> feedback -> promotion.
- Upgraded `app-export` and `app-serve` to expose `dashboard.json`,
  `timeline.json`, `/api/dashboard`, and `/api/timeline` for the future EXE UI.
- Upgraded approval preview cards with safe next steps and exact approve,
  block, or execute commands.
- Added `delegation workspace-init` and `delegation workspace-status` so any
  local folder can become a no-GitHub DelegationHQ workspace with a Harnessfile,
  Agent Passport registry, and optional dry-run ledger.
- Added `delegation agent-add` so users can register CLI/API/webhook/MCP-style
  custom agents without hand-editing a large YAML file.
- Added `delegation agent-run` so command-backed custom agents can be gated,
  executed after exact confirmation, and recorded with local evidence.
- Added workspace defaults for `agent-add`, `agent-run`, `app-state`, and
  `cockpit` so the local app path can start from a folder instead of a pile of
  internal ledger and registry flags.
- Added `delegation approval-preview`, `delegation app-export`, and
  `delegation app-serve` so a workspace can produce a human approval card and a
  local browser cockpit shell without live execution.
- Added `delegation demo --control-loop` so one install-safe command now shows
  the plan -> gate -> approval -> RunPrint recording -> audit path.
- Added `delegation mission-status` for a plain operator view over one ledger:
  plan, gate, approval, proof, attention, and next action.
- Added `delegation agent-packet` to export a Bring Your Own Agent handoff card
  from an Agent Gate receipt.
- Added Agent Gate ledger receipts and `delegation agent-audit` so a mission
  can compare what an agent asked to do with planned or recorded RunPrint
  evidence.
- Added `delegation approval-inbox` and `delegation approval-decision` so Agent
  Gate receipts become simple human approve/block cards backed by ledger
  evidence.
- Added `delegation runprint-ingest` so external RunPrint recording evidence
  can be attached to the exact Agent Gate receipt and make audits say
  `recorded`.
- Added `delegation agent-gate` for Agent Passport action previews. It returns
  `allow`, `warn`, `approval_required`, or `block`, supports Harnessfile and
  custom registry agents, and feeds gate-ready JSON into `app-state`.
- Hardened `github.actions` live dispatch with workflow metadata preflight,
  active duplicate-run protection, dispatch-time rechecks, cancellation guidance
  in ledger evidence, and focused fake-client tests.
- Added `delegation app-state` as one read-only state bundle for the future
  local cockpit, combining app plan, doctor, release readiness, mission
  snapshot, evidence bundles, next action, and guardrails.
- Added `delegation agents` for Agent Passport registry reporting across
  Harnessfile agents and custom Bring Your Own Agent registry files.
- Added `delegation release-check` for local alpha release-readiness reports
  that do not publish, tag, or call external services.
- Added `delegation github-app-plan` for local GitHub App permission and
  scoped installation-token planning before live app auth exists.
- Added `delegation apply-feedback` for gated feedback recovery comments and
  optional issue closing with separate confirmation tokens.
- Added the first GitHub App issue-write auth boundary for live issue commands
  through `--auth github-app`.
- Added optional `delegation doctor --github-app` diagnostics for local GitHub
  App auth setup without minting a token.
- Added `delegation cancel-actions` with preview-first GitHub Actions
  cancellation, force-cancel confirmation, token diagnostics, optional ledger
  evidence, and fake-client tests.
- Added ledger-based GitHub Actions dispatch idempotency with stable
  secret-safe dispatch ids and duplicate-dispatch blocking.
- Added `delegation artifacts` for release checksum and artifact-manifest
  generation, wired it into the Windows EXE build path, and verified stale
  checksum detection.
- Added `delegation release-rehearse` for a local evidence bundle that captures
  release readiness, artifact verification, git state, metadata, and next steps
  without publishing anything.
- Added `delegation app-plan` for the first visible Windows EXE mission-cockpit
  plan, including Bring Your Own Agent passport direction.
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
