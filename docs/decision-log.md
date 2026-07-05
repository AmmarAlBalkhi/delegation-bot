# Decision Log

## 2026-07-03: Reframe As An AI Harness Control Plane

Decision: Evolve Delegation Bot beyond GitHub Issue creation into a repo-native
control plane for delegated work across humans, scripts, agents, and AI
harnesses.

Why: The durable product surface is not a single executor. It is the layer that
defines objectives, context, policies, approvals, outputs, evidence, and evals
before any executor runs.

Evidence:

- `docs/vision.md`
- `docs/architecture.md`
- `examples/ai-harness-control-plane.yaml`
- `scripts/harness_manifest.py`

## 2026-07-03: Add Manifest Validation Before Execution

Decision: Introduce a v1 Harnessfile validator before adding live execution.

Why: A revolutionary tool still needs boring foundations. Validation lets us
move toward orchestration while keeping the execution surface inspectable and
testable.

Evidence:

- `schemas/harness.v1.schema.json`
- `scripts/harness_manifest.py`
- `tests/test_harness_manifest.py`

## 2026-07-03: Standardize QA And Backups

Decision: Add first-class QA and backup commands.

Why: The project is about trustworthy delegation. Its own development workflow
should model the same values: recoverability, repeatability, and visible
evidence.

Evidence:

- `scripts/qa.py`
- `scripts/backup_repo.py`
- `docs/qa.md`

## 2026-07-03: Add Agent Operating Rules

Decision: Add repo-local instructions for future AI agents.

Why: A project about harnessing delegated intelligence should make its own
agent behavior explicit. `AGENTS.md` gives future agents a concise operating
manual for backups, QA, typed changes, documentation, and completion evidence.

Evidence:

- `AGENTS.md`

## 2026-07-03: Frame The Million-Star Roadmap

Decision: Add a public roadmap and deeper strategy document that frame the path
from task bot to AI delegation control plane.

Why: The project needs a clear open-source story before adding more machinery.
The plan treats stars as a lagging signal of trust and adoption, not a vanity
target.

Evidence:

- `ROADMAP.md`
- `docs/million-star-strategy.md`

## 2026-07-03: Add Dry-Run Plan Compiler And Ledger

Decision: Add a typed `delegation plan` path that compiles a Harnessfile into a
readable dry-run plan and optional JSONL run ledger.

Why: This is the first real mission-control primitive. Users can inspect what
would happen before any GitHub write, agent execution, network call, or model
request occurs.

Evidence:

- `scripts/delegation.py`
- `scripts/harness_plan.py`
- `schemas/ledger.v1.schema.json`
- `tests/test_harness_plan.py`
- `tests/test_delegation_cli.py`

## 2026-07-03: Add Agent Enablement Layer

Decision: Add agent passports, capability packs, and autonomy levels to the
Harnessfile and planner.

Why: The project should enable AI, not merely suppress it. Agents need a path to
more useful autonomy through explicit powers, clear runtime identity, and
promotion rules backed by evals and run ledgers.

Evidence:

- `docs/agent-enablement.md`
- `examples/ai-harness-control-plane.yaml`
- `scripts/harness_manifest.py`
- `scripts/harness_plan.py`
- `schemas/harness.v1.schema.json`
- `tests/test_harness_manifest.py`
- `tests/test_harness_plan.py`

## 2026-07-03: Add Promotion Evaluator

Decision: Add a `delegation promote` command that checks whether agents are
ready for their declared next autonomy level.

Why: Promotion should be based on evidence, not vibes. The evaluator reads
passed eval events from the ledger and blocks promotion when required eval
evidence is missing.

Evidence:

- `scripts/promotion.py`
- `schemas/promotion-report.v1.schema.json`
- `tests/test_promotion.py`
- `tests/test_delegation_cli.py`

## 2026-07-03: Add Built-In Eval Runner

Decision: Add `delegation eval` to run built-in checks against a ledger and
optionally append `eval.result` events.

Why: Promotion needs real evidence. Planned evals are not enough. The first eval
runner gives the ledger a way to record concrete pass, fail, or blocked results.

Evidence:

- `scripts/evals.py`
- `schemas/eval-report.v1.schema.json`
- `tests/test_evals.py`
- `tests/test_delegation_cli.py`

## 2026-07-03: Add Adapter Contract Registry

Decision: Add built-in adapter contracts and a CLI command for listing and
inspecting them.

Why: The project should become a harness for AI harnesses without coupling the
Harnessfile to one agent runtime. Adapter contracts give each backend a simple,
testable promise: required inputs, possible outputs, risk level, approval
requirements, ledger events, and required evidence.

Evidence:

- `scripts/adapters.py`
- `schemas/adapter-contract.v1.schema.json`
- `docs/adapter-contracts.md`
- `tests/test_adapters.py`
- `tests/test_harness_plan.py`
- `tests/test_delegation_cli.py`

## 2026-07-04: Add Packaging And License Planning

Decision: Add Python package metadata, a `delegation` console command, a
changelog, release checklist, and license strategy document.

Why: The project is intended for other users, not only local scripts. Packaging
metadata gives early adopters a normal install path, while the license strategy
made the license posture explicit before the later Apache-2.0 decision.

Evidence:

- `pyproject.toml`
- `CHANGELOG.md`
- `docs/release.md`
- `docs/license-strategy.md`
- `README.md`

## 2026-07-04: Move Core Code Into Package Namespace

Decision: Add the installable `delegation_bot` package namespace and keep
`scripts/*.py` compatibility wrappers.

Why: Other users should not depend on a loose scripts directory as the product
surface. A real package namespace makes installs, console entry points, module
execution, and future API documentation cleaner while preserving the old local
commands.

Evidence:

- `delegation_bot/`
- `scripts/delegation.py`
- `pyproject.toml`
- `tests/test_package_namespace.py`
- `scripts/qa.py`

## 2026-07-04: Choose Apache-2.0 License

Decision: Move the project license from MIT to Apache-2.0 and add a project
`NOTICE` file.

Why: Delegation Bot is becoming infrastructure for agentic AI. Apache-2.0 keeps
the open-source core permissive and business-friendly, while adding clearer
patent protection, contribution treatment, and attribution than MIT.

Evidence:

- `LICENSE`
- `NOTICE`
- `pyproject.toml`
- `docs/license-strategy.md`
- `scripts/qa.py`

## 2026-07-04: Add Public Contribution Surface

Decision: Add contribution, support, security, pull request, issue-template,
and domain-strategy documents.

Why: A project meant for public users needs clear collaboration paths before a
domain, launch, or package release sends people to the repository.

Evidence:

- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `SUPPORT.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/ISSUE_TEMPLATE/`
- `docs/domain-strategy.md`

## 2026-07-04: Add Anthropic And Business Planning Notes

Decision: Add explicit Anthropic Claude and Claude Code adapter contracts, plus
business-model and next-action planning documents.

Why: Claude is a major model and coding-agent surface, so it should not be
implicit. The business plan should be documented, but kept separate from the
core engineering queue so the project stays focused on Harnessfile, plan,
policy, adapter, ledger, eval, and promotion primitives.

Evidence:

- `delegation_bot/adapters.py`
- `examples/ai-harness-control-plane.yaml`
- `docs/adapter-contracts.md`
- `docs/business-model.md`
- `docs/next-actions.md`
- `tests/test_adapters.py`

## 2026-07-04: Add Adapter SDK And First Dry-Run Adapter

Decision: Add a small adapter SDK with request, result, event, validation, and
contract-backed dry-run primitives. Implement `github.issue` as the first
SDK-backed dry-run adapter and connect it to dry-run ledger generation.

Why: Adapter contracts describe the promise, but implementations need a shared
shape. The SDK turns Delegation Bot from "we can list harnesses" into "harnesses
can plug in and prove their outputs, events, and evidence."

Evidence:

- `delegation_bot/adapter_sdk.py`
- `delegation_bot/builtin_adapters.py`
- `delegation_bot/harness_plan.py`
- `docs/adapter-sdk.md`
- `tests/test_adapter_sdk.py`
- `tests/test_harness_plan.py`

## 2026-07-04: Add Ledger Viewer Command

Decision: Add `delegation ledger` for reading JSONL run ledgers as a human
report or JSON view.

Why: The ledger is the durable evidence trail for plans, adapter actions,
approvals, evals, and future live execution. Users should not need to inspect
raw JSONL to understand what happened or what evidence an adapter produced.

Evidence:

- `delegation_bot/ledger.py`
- `delegation_bot/cli.py`
- `docs/ledger-viewer.md`
- `tests/test_ledger.py`
- `tests/test_delegation_cli.py`
- `scripts/qa.py`

## 2026-07-04: Add Required Adapter Evidence Eval

Decision: Add the `required_adapter_evidence` eval to verify SDK-backed adapter
results against their adapter contracts.

Why: Adapter evidence should be more than visible. It should be testable. This
eval checks that SDK-backed adapter results match a known contract, include
required evidence, include required outputs, and reached a planned or succeeded
state.

Evidence:

- `delegation_bot/evals.py`
- `examples/ai-harness-control-plane.yaml`
- `docs/ledger-viewer.md`
- `tests/test_evals.py`

## 2026-07-04: Add No-Network Sample Adapter

Decision: Add the `sample.echo` adapter contract and SDK-backed dry-run
implementation, plus a 30-minute adapter author guide.

Why: The adapter SDK needs a safe contributor path. A no-network sample lets new
adapter authors test the full loop without secrets, external APIs, or live
execution: contract, dry-run result, ledger evidence, evals, and QA.

Evidence:

- `delegation_bot/adapters.py`
- `delegation_bot/builtin_adapters.py`
- `examples/ai-harness-control-plane.yaml`
- `docs/build-an-adapter.md`
- `tests/test_adapter_sdk.py`
- `tests/test_harness_plan.py`

## 2026-07-04: Add Compact Ledger Fixtures

Decision: Add small JSONL fixtures for good, blocked, and failed adapter result
states.

Why: Contributors need examples they can read without running a full workflow.
The fixtures make the adapter result contract, ledger viewer, and
`required_adapter_evidence` eval concrete.

Evidence:

- `examples/ledgers/adapter-good.jsonl`
- `examples/ledgers/adapter-blocked.jsonl`
- `examples/ledgers/adapter-failed.jsonl`
- `docs/ledger-fixtures.md`
- `tests/test_ledger_fixtures.py`

## 2026-07-04: Add README 60-Second Demo

Decision: Rewrite the README opening around a fast dry-run demo.

Why: New visitors should understand the project before reading architecture
docs. The README now shows the core loop directly: plan, ledger, eval, promote,
plus compact ledger fixtures.

Evidence:

- `README.md`
- `docs/next-actions.md`
- `ROADMAP.md`

## 2026-07-04: Add Starter Playbooks

Decision: Add the first reusable Harnessfile playbooks for code review, CI
repair, and documentation refresh.

Why: The million-star idea needs copyable workflows, not only architecture.
Playbooks show how the control-plane loop works for real agentic jobs:
planning, issue coordination, adapter evidence, policy gates, evals, and future
promotion.

Evidence:

- `playbooks/code-review.yaml`
- `playbooks/ci-repair.yaml`
- `playbooks/documentation-refresh.yaml`
- `docs/playbooks.md`
- `tests/test_playbooks.py`
- `scripts/qa.py`

## 2026-07-04: Add Evidence Artifacts, More Dry-Run Adapters, Fixtures, Feedback Notes, And Catalog Metadata

Decision: Complete the next five control-plane moves: upload workflow run
evidence as a GitHub Actions artifact, add SDK-backed dry-run adapters for
`mcp.tool`, `openai.agents`, `anthropic.messages`, and `claude.code`, add an
adapter fixture generator, document the eval-to-issue feedback loop, and add
playbook catalog metadata.

Why: These changes strengthen the same core loop instead of adding random
features. Users get downloadable evidence, more harness coverage, repeatable
adapter examples, a path from failures to improvement issues, and a searchable
playbook index.

Evidence:

- `.github/workflows/delegation.yml`
- `delegation_bot/builtin_adapters.py`
- `delegation_bot/adapter_fixtures.py`
- `delegation_bot/playbook_catalog.py`
- `scripts/generate_adapter_fixtures.py`
- `docs/eval-to-issue-feedback.md`
- `playbooks/catalog.yaml`
- `schemas/playbook-catalog.v1.schema.json`
- `tests/test_adapter_fixtures.py`
- `tests/test_playbook_catalog.py`
- `tests/test_workflows.py`

## 2026-07-04: Complete Local Dry-Run Operating Loop

Decision: Add SDK-backed dry-run adapters for `github.actions`,
`codex.thread`, and `local.classifier`, implement `delegation feedback` for
dry-run GitHub Issue drafts from eval evidence, and add `delegation catalog`
for playbook discovery.

Why: These three moves make the control-plane loop more useful without enabling
unsafe live execution. The system can now plan code handoffs, verification
workflows, local risk classification, failed-eval feedback issues, and playbook
discovery from one CLI.

Evidence:

- `delegation_bot/builtin_adapters.py`
- `delegation_bot/eval_feedback.py`
- `delegation_bot/cli.py`
- `examples/ai-harness-control-plane.yaml`
- `docs/eval-to-issue-feedback.md`
- `tests/test_adapter_sdk.py`
- `tests/test_eval_feedback.py`
- `tests/test_delegation_cli.py`

## 2026-07-04: Harden Evidence, Complete Dry-Run Adapters, And Map Observability

Decision: Upload stronger workflow evidence artifacts, add dry-run
implementations for every remaining built-in adapter contract, group repeated
eval feedback by marker, and document the first OpenTelemetry mapping.

Why: The project is becoming a trust layer. That means every demo and CI run
should leave inspectable proof, every built-in contract should produce concrete
dry-run evidence, repeated failures should not create noise, and the ledger
should have a clear path into standard observability tools.

Evidence:

- `.github/workflows/delegation.yml`
- `.github/workflows/tests.yml`
- `delegation_bot/builtin_adapters.py`
- `delegation_bot/eval_feedback.py`
- `examples/ai-harness-control-plane.yaml`
- `docs/opentelemetry-mapping.md`
- `tests/test_adapter_sdk.py`
- `tests/test_eval_feedback.py`
- `tests/test_workflows.py`

## 2026-07-04: Preserve Product Positioning

Decision: Add a dedicated positioning document for the mission-control framing,
uniqueness argument, use cases, adjacent-tool map, and marketing hooks.

Why: The project needs to stay centered while implementation expands. The
durable idea is not "another agent framework"; it is an AI delegation control
plane above many harnesses, with dry-runs, policy gates, evidence, evals, and
agent promotion.

Evidence:

- `docs/positioning.md`
- `README.md`
- `docs/million-star-strategy.md`

## 2026-07-04: Add Flagship Playbooks And Live-Gate Design

Decision: Add the release-readiness flagship playbook, a weekly-planning
playbook, an adapter compatibility matrix, and the first live-execution gate
design for `github.issue`.

Why: The project needs one undeniable demo loop, not only a set of primitives.
Release readiness ties together metadata, license, changelog, QA, adapters,
approval, ledger evidence, evals, and promotion. Weekly planning proves the
same control plane can support recurring team workflows. The live gate keeps the
next execution step narrow and safe.

Evidence:

- `playbooks/release-readiness.yaml`
- `playbooks/weekly-planning.yaml`
- `playbooks/catalog.yaml`
- `docs/adapter-compatibility.md`
- `docs/live-execution-gate.md`
- `docs/playbooks.md`
- `README.md`

## 2026-07-04: Make The Hybrid Trust Model Explicit

Decision: Promote the hybrid principle into the core product docs:

```text
AI proposes.
Delegation Bot verifies.
Human approves risky actions.
Ledger records everything.
Evals decide whether trust increases.
```

Why: The project should enable AI without letting AI approve itself. Model-backed
features can draft Harnessfiles, recommend adapters, explain plans, summarize
ledgers, and propose fixes, but deterministic code should own validation, policy
gates, approval requirements, ledger writes, eval results, and promotion
readiness.

Evidence:

- `docs/hybrid-trust-model.md`
- `docs/positioning.md`
- `docs/architecture.md`
- `docs/next-actions.md`
- `README.md`

## 2026-07-04: Add Low-Friction Product Experience Principles

Decision: Add a dedicated product-experience guide and link it from the public
README and planning docs.

Why: A trust layer can become tedious if every safety feature feels like extra
paperwork. Delegation Bot should be useful in 60 seconds, powerful after 10
minutes, and deep only when users ask for depth. The product should start from
goals, playbooks, examples, and AI-drafted Harnessfiles, then reveal policy,
ledger, and eval detail progressively.

Evidence:

- `docs/product-experience.md`
- `README.md`
- `docs/positioning.md`
- `docs/next-actions.md`
- `docs/vision.md`
- `ROADMAP.md`

## 2026-07-04: Move Legacy Task-Bot Examples Out Of The Main Path

Decision: Move the original rule-based recurring task examples from `tasks/`
to `examples/legacy-recurring-tasks/`, label `scripts/delegation_bot.py` as the
legacy compatibility entry point, and update README/architecture docs so new
visitors see the Harnessfile control plane first.

Why: The old proof of concept still has value, but it can confuse the first
impression. Delegation Bot should now read as mission control for agentic work,
not just a recurring GitHub Issue bot.

Evidence:

- `examples/legacy-recurring-tasks/`
- `examples/legacy-recurring-tasks/README.md`
- `scripts/delegation_bot.py`
- `README.md`
- `docs/architecture.md`

## 2026-07-04: Add Template-Backed Harnessfile Suggestions

Decision: Add `delegation suggest`, a no-network command that drafts a valid
Harnessfile from a plain-language goal and can immediately compile a dry-run
plan and ledger.

Why: The project needs a fast first-run path that does not start from a blank
YAML file. This preserves the hybrid trust model: suggestions make AI
delegation easier, but deterministic validation, planning, ledgers, evals, and
human approval still control trust.

Evidence:

- `delegation_bot/suggest.py`
- `delegation_bot/cli.py`
- `docs/harnessfile-suggest.md`
- `tests/test_suggest.py`
- `tests/test_delegation_cli.py`
- `scripts/qa.py`

## 2026-07-04: Keep Model-Backed Suggestions Explicit

Decision: Document model-backed `delegation suggest` as an explicit opt-in path
and add a structured draft schema for future model output. Also add a repeat
threshold for blocked eval feedback so one blocked dry-run does not immediately
become issue noise.

Why: The product should enable AI without letting AI approve itself. Models can
draft Harnessfiles through OpenAI, Anthropic, or local providers, but the
deterministic control plane still validates, plans, writes ledgers, runs evals,
and controls promotion. Blocked evals should be helpful signals, not chores.

Evidence:

- `docs/model-backed-suggest.md`
- `schemas/harness-suggestion-draft.v1.schema.json`
- `delegation_bot/eval_feedback.py`
- `delegation_bot/cli.py`
- `docs/eval-to-issue-feedback.md`
- `tests/test_eval_feedback.py`

## 2026-07-04: Add Local Readiness Doctor

Decision: Add `delegation doctor` as the local readiness check before live
execution work.

Why: The control plane should feel powerful without making users guess what is
working. Doctor checks Python, dependencies, package metadata, license files,
schemas, the flagship Harnessfile, the suggest-to-plan loop, ledger fixtures,
Git, and optional GitHub CLI auth. This makes the next live `github.issue` gate
safer because users can see whether their setup is ready before any write.

Evidence:

- `delegation_bot/doctor.py`
- `delegation_bot/cli.py`
- `docs/doctor.md`
- `README.md`
- `tests/test_doctor.py`
- `tests/test_delegation_cli.py`
- `scripts/qa.py`

## 2026-07-04: Add First Live GitHub Issue Gate

Decision: Add `delegation apply-issues` as the first live execution path. The
command previews gates by default and only writes GitHub Issues when the user
passes `--apply --confirm LIVE_GITHUB_ISSUES` with a GitHub token.

Why: The project needs real action, but not uncontrolled action. A GitHub Issue
is visible and reversible compared with model calls, coding agents, workflow
runs, or deployments. This proves the live-gate pattern while keeping the
control plane's core promise: dry-run first, policy gates, explicit intent,
ledger evidence, then live apply.

Evidence:

- `delegation_bot/github_issue_apply.py`
- `delegation_bot/cli.py`
- `docs/github-issue-apply.md`
- `docs/live-execution-gate.md`
- `tests/test_github_issue_apply.py`
- `tests/test_delegation_cli.py`
- `scripts/qa.py`

## 2026-07-04: Clarify Star Milestones As Aspirational

Decision: Rename roadmap star milestones as aspirational target states and add
a short humility note to the million-star strategy.

Why: The project should be ambitious without pretending to have traction it does
not yet have. Stars are a lagging signal of legitimate adoption, not the thing
to fake or optimize directly.

Evidence:

- `ROADMAP.md`
- `docs/million-star-strategy.md`

## 2026-07-04: Add Local Telemetry Export And Provider Fixtures

Decision: Add `delegation otel`, no-network OpenAI and Anthropic model-backed
suggestion fixtures, an applied `github.issue` ledger fixture, README artifact
download guidance, and TestPyPI dry-run notes.

Why: The next product layer should keep strengthening the core loop. Telemetry
export lets teams carry Delegation Bot evidence into observability systems
later. Provider fixtures let model-backed suggestions be tested without cost or
network calls. Applied issue fixtures make the live gate lifecycle concrete.
TestPyPI notes prepare the project for users without rushing a release.

Evidence:

- `delegation_bot/otel_export.py`
- `delegation_bot/model_suggest_fixtures.py`
- `examples/model-suggestions/`
- `examples/ledgers/github-issue-applied.jsonl`
- `docs/opentelemetry-mapping.md`
- `docs/model-backed-suggest.md`
- `docs/testpypi-dry-run.md`
- `tests/test_otel_export.py`
- `tests/test_model_suggest_fixtures.py`

## 2026-07-05: Add Direct Eval-To-Feedback Drafts

Decision: Add direct `EvalResult` to feedback issue draft conversion and expose
it through `delegation eval --feedback`.

Why: The feedback loop should not make users perform extra ceremony. Failed or
blocked evals should be easy to turn into clear, deduped improvement issue
drafts immediately after the eval run, while live GitHub writes remain behind
the existing apply gate.

Evidence:

- `delegation_bot/eval_feedback.py`
- `delegation_bot/cli.py`
- `docs/eval-to-issue-feedback.md`
- `tests/test_eval_feedback.py`
- `tests/test_delegation_cli.py`
- `scripts/qa.py`

## 2026-07-05: Improve Discovery And Contributor Readiness

Decision: Add playbook catalog filtering by tag and adapter, document the first
hosted dashboard wireframe, and write the contributor license and DCO policy
notes.

Why: The project already has powerful control-plane primitives, but new users
need a clearer doorway. Catalog filtering helps people pick the right mission
quickly, dashboard notes keep future UI tied to the CLI loop, and contributor
policy notes make public collaboration understandable without adding early CLA
friction.

Evidence:

- `delegation_bot/playbook_catalog.py`
- `delegation_bot/cli.py`
- `docs/playbooks.md`
- `docs/dashboard-wireframe.md`
- `docs/contributor-license-policy.md`
- `CONTRIBUTING.md`
- `tests/test_playbook_catalog.py`
- `tests/test_delegation_cli.py`
- `scripts/qa.py`

## 2026-07-05: Curate Public Roadmap And Contributor Triage

Decision: Add public roadmap issue drafts, a label source of truth,
good-first-issue curation rules, stronger issue templates, and GitHub App
installation design notes.

Why: The repository should look clean and intentional before more people arrive.
Roadmap issues need to guide contributors toward useful work without reviving
the old noisy task list. GitHub App planning also needs to happen before the
project asks users for scoped repository access.

Evidence:

- `docs/public-roadmap-issues.md`
- `docs/issue-labels.md`
- `docs/github-app-installation.md`
- `.github/labels.yml`
- `.github/ISSUE_TEMPLATE/`
- `CONTRIBUTING.md`
- `README.md`
- `docs/next-actions.md`

## 2026-07-05: Add Opt-In Live Model Suggestions

Decision: Add live OpenAI and Anthropic provider paths for `delegation suggest`,
guarded by `--allow-live-model`, provider API-key checks, draft envelope
validation, normal Harnessfile validation, and deterministic dry-run planning.

Why: The product should enable AI, not suppress it. Users should be able to ask
AI for a Harnessfile draft, but the control plane must still own trust:
validation, policy gates, ledger writes, evals, and human approval. The default
output also became shorter so the first run feels useful instead of like
homework.

Evidence:

- `delegation_bot/model_suggest_live.py`
- `delegation_bot/cli.py`
- `delegation_bot/model_suggest_fixtures.py`
- `docs/model-backed-suggest.md`
- `docs/harnessfile-suggest.md`
- `tests/test_model_suggest_live.py`
- `tests/test_delegation_cli.py`
