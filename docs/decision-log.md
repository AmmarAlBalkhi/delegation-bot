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

## 2026-07-03: Frame The Adoption Roadmap

Decision: Add a public roadmap and deeper strategy document that frame the path
from task bot to AI delegation control plane.

Why: The project needs a clear open-source story before adding more machinery.
The plan treats stars as a lagging signal of trust and adoption, not a vanity
target.

Evidence:

- `ROADMAP.md`
- `docs/adoption-strategy.md`

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

Why: The adoption strategy needs copyable workflows, not only architecture.
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
- `docs/adoption-strategy.md`

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
a short humility note to the adoption strategy.

Why: The project should be ambitious without pretending to have traction it does
not yet have. Stars are a lagging signal of legitimate adoption, not the thing
to fake or optimize directly.

Evidence:

- `ROADMAP.md`
- `docs/adoption-strategy.md`

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

## 2026-07-05: Remember Live Feedback Issues

Decision: Link eval feedback drafts to live GitHub issue numbers and URLs when
prior apply events exist, and allow intentional feedback update lifecycles in
the duplicate marker eval.

Why: The feedback loop should make the project smarter without creating issue
noise. If an eval failure already became issue #321, the next matching failure
should draft an update to #321. This keeps control and learning visible while
still avoiding duplicate public clutter.

Decision: Delay importing live network dependencies until live GitHub apply or
live model calls need them.

Why: Read-only commands such as `delegation ledger` should work for first-time
users and contributors even before optional network dependencies are installed.

Evidence:

- `delegation_bot/eval_feedback.py`
- `delegation_bot/builtin_adapters.py`
- `delegation_bot/evals.py`
- `delegation_bot/github_issue_apply.py`
- `delegation_bot/model_suggest_live.py`
- `examples/ledgers/feedback-issue-memory.jsonl`
- `docs/eval-to-issue-feedback.md`
- `docs/github-issue-apply.md`
- `tests/test_eval_feedback.py`
- `tests/test_evals.py`
- `tests/test_ledger_fixtures.py`

## 2026-07-05: Prioritize Adapters, Dashboard Data, And Feedback Recovery

Decision: Add a researched adapter candidate matrix before adding more adapter
surface area.

Why: Delegation Bot should be a harness for AI harnesses, not a random pile of
integrations. The matrix ranks candidates by user pull, evidence value,
dry-run clarity, risk, and contributor fit so new adapters strengthen the core
control-plane loop.

Decision: Add `delegation dashboard` as a read-only data model before any
dashboard UI design.

Why: The user experience should become easier without making the project feel
generic. A stable snapshot lets future UI work show mission, eval, adapter,
feedback, and agent state without bypassing Harnessfiles, ledgers, or approval
gates.

Decision: Add `delegation recover-feedback` so passing evals can draft recovery
updates for existing live feedback issues.

Why: The feedback loop should close the learning cycle. Failed evals create or
update issues; passing evals should help humans resolve those issues without
automatic closure or hidden live writes.

Evidence:

- `docs/adapter-candidate-matrix.md`
- `delegation_bot/dashboard.py`
- `delegation_bot/eval_feedback.py`
- `delegation_bot/cli.py`
- `docs/dashboard-data-model.md`
- `docs/eval-to-issue-feedback.md`
- `examples/ledgers/feedback-recovery.jsonl`
- `tests/test_dashboard.py`
- `tests/test_eval_feedback.py`
- `tests/test_delegation_cli.py`
- `tests/test_ledger_fixtures.py`

## 2026-07-05: Preview GitHub Actions Dispatch Before Live Runs

Decision: Add `delegation apply-actions` as a preview-first gate for
`github.actions` workflow dispatch.

Why: GitHub Actions is a real execution surface. Running a workflow can trigger
tests, release jobs, deployments, artifacts, and follow-on automation. The next
safe product step is to show exactly which workflow, ref, inputs, and run URL
shape would be used, then stop before live dispatch.

Decision: Require `workflow_run_url` evidence in the `github.actions` contract.

Why: A run id alone is not enough for a human-friendly control plane. Users need
a clickable place where the future run would be inspected. The dry-run URL is
preview evidence today and prepares the ledger shape for a future live dispatch
client.

Evidence:

- `delegation_bot/github_actions_apply.py`
- `delegation_bot/builtin_adapters.py`
- `delegation_bot/adapters.py`
- `delegation_bot/cli.py`
- `examples/ledgers/github-actions-preview.jsonl`
- `docs/github-actions-apply.md`
- `docs/live-execution-gate.md`
- `tests/test_github_actions_apply.py`
- `tests/test_delegation_cli.py`
- `tests/test_ledger_fixtures.py`

## 2026-07-05: Make MCP Tool Risk Visible Before Tool Use

Decision: Strengthen `mcp.tool` dry-run evidence with `permission_scope`,
`risk_level`, `prompt_injection_risk`, `recommended_gate`, capability tags, and
plain-language risk reasons.

Why: MCP tools are meant to let models interact with external systems. That is
useful and dangerous. Delegation Bot should enable tool use, but the run ledger
must show what kind of power the tool is asking for before any live invocation.

Decision: Add `mcp_tool_risk_review` as a deterministic eval.

Why: The adapter should write facts, and evals should make those facts useful.
High-risk tool plans now become a clear blocked eval instead of hidden
metadata.

Evidence:

- `delegation_bot/builtin_adapters.py`
- `delegation_bot/adapters.py`
- `delegation_bot/evals.py`
- `examples/ledgers/mcp-tool-risk.jsonl`
- `docs/mcp-tool-risk.md`
- `tests/test_adapter_sdk.py`
- `tests/test_evals.py`
- `tests/test_ledger_fixtures.py`

## 2026-07-05: Make MCP Policy And Demo Easier To Try

Decision: Add `delegation mcp-gate` as a friendly report over MCP tool
allowlists and risk evidence.

Why: Risk evidence is useful only if users can act on it quickly. The command
turns ledger evidence into a plain allowed/blocked report with next actions for
missing `allowed_mcp_servers`, missing `allowed_mcp_tools`, and missing
approval evidence.

Decision: Add a 60-second demo guide and a Windows EXE packaging plan.

Why: Delegation Bot needs to become usable soon, not only architecturally
interesting. The demo shows the core product promise quickly, and the EXE plan
starts the path toward a download-and-run Windows experience without claiming
that artifact exists yet.

Evidence:

- `delegation_bot/mcp_policy_gate.py`
- `delegation_bot/cli.py`
- `docs/demo.md`
- `docs/windows-exe.md`
- `pyproject.toml`
- `examples/ai-harness-control-plane.yaml`
- `tests/test_mcp_policy_gate.py`
- `tests/test_delegation_cli.py`

## 2026-07-05: Make The First Run A Real Product Moment

Decision: Add `delegation demo` as a one-command, install-safe mission-control
demo.

Why: A new user should not need to understand Harnessfile structure before the
idea clicks. The demo writes a dry-run ledger, checks MCP policy, previews
GitHub Actions dispatch, and runs evals without relying on source-repo example
files.

Decision: Add `delegation init` for starter Harnessfiles.

Why: Users should be able to start from a plain-language goal instead of a blank
YAML file. The command detects the GitHub origin when possible, refuses to
overwrite by default, and can optionally compile the starter into a ledger.

Decision: Add an installed-package demo smoke test.

Why: The future `.exe` and public package need the same proof: after install,
the product can run from outside the source checkout and show the core value
quickly.

Evidence:

- `delegation_bot/first_run.py`
- `delegation_bot/cli.py`
- `scripts/package_smoke.py`
- `scripts/qa.py`
- `docs/demo.md`
- `docs/product-experience.md`
- `docs/release.md`
- `docs/windows-exe.md`
- `tests/test_delegation_cli.py`

## 2026-07-05: Add Local Model Harnessfile Drafting

Decision: Add `ollama` as an opt-in live model provider for `delegation
suggest`.

Why: Delegation Bot should enable AI without forcing every AI draft through a
hosted provider. Ollama gives privacy-sensitive users a local model path while
the control plane keeps the same trust boundary: the model proposes, then
Delegation Bot validates, dry-runs, writes the ledger, and runs evals.

Decision: Keep local model drafting behind `--allow-live-model`.

Why: A local model call has no hosted API key, but it still reads prompt
context, can be slow, and can return bad output. The explicit flag keeps the
product honest: no hidden model calls, even local ones.

Evidence:

- `delegation_bot/model_suggest_live.py`
- `delegation_bot/model_suggest_fixtures.py`
- `delegation_bot/cli.py`
- `schemas/harness-suggestion-draft.v1.schema.json`
- `docs/model-backed-suggest.md`
- `docs/harnessfile-suggest.md`
- `tests/test_model_suggest_live.py`
- `tests/test_delegation_cli.py`

## 2026-07-05: Add Windows EXE Build Script

Decision: Add `scripts\build-windows-exe.ps1` as the first executable build
path.

Why: The product should become easy to try without forcing new users to learn
Python packaging first. A Windows `.exe` supports that goal, but it must still
ship the same safe first-run loop: demo, starter Harnessfile init, validation,
and no live writes by default.

Evidence: The script builds `dist\delegation.exe` with PyInstaller, bundles
runtime assets used by demos and fixtures, and runs safe demo/init/validate
smoke checks before reporting success. A local Windows build passed on
2026-07-05.

## 2026-07-05: Add Local Classifier Policy Profiles

Decision: Add deterministic policy profiles to `local.classifier`.

Why: Delegation Bot should enable local AI and local classification, but the
trust boundary must stay clear. A classifier can explain risk and recommend a
gate, while deterministic profiles, approval gates, ledger evidence, and evals
remain responsible for trust decisions.

Evidence: `local.classifier` now emits `policy_profile`, `recommended_gate`,
matched terms, and reasons. Release-readiness paths use a stricter
`release-readiness` profile, while general first-run paths use
`delegation.default`.

## 2026-07-06: Enable Gated GitHub Actions Live Dispatch

Decision: Move `delegation apply-actions` from preview-only to preview-first
live dispatch.

Why: GitHub Actions is the first higher-power execution surface that still has a
small, inspectable request shape: repository, workflow file, ref, and inputs.
GitHub's current workflow dispatch API returns run identifiers and URLs, which
fit the run-ledger evidence model.

Guardrails:

- preview remains the default
- live mode requires `--apply --confirm LIVE_GITHUB_ACTIONS`
- live mode requires `GITHUB_TOKEN` or `GH_TOKEN`
- repository policy, ledger validity, adapter evidence, and approval gates still
  run before dispatch
- workflow inputs are capped at GitHub's 25-key limit
- dispatch results append `github.actions.*` ledger events

Follow-up: Add token-scope diagnostics and a dedicated cancel command after the
preflight hardening lands.

## 2026-07-06: Harden GitHub Actions Live Dispatch

Decision: Add live dispatch preflight checks before `github.actions` workflow
dispatch.

Why: Once a workflow can be dispatched, the next risk is pressing the wrong
button or pressing the same button twice. The bot should verify the workflow is
real, active, under `.github/workflows/`, and not already running for the same
workflow/ref before it sends another dispatch request.

What changed:

- live mode fetches workflow metadata before dispatch
- disabled or unexpected workflow paths block dispatch
- active `workflow_dispatch` runs for the same workflow/ref block dispatch
- dispatch rechecks preflight immediately before pressing run
- dispatched ledger events include cancel and force-cancel API paths

Follow-up: Add token-scope diagnostics and a dedicated cancel command behind its
own explicit confirmation token.

## 2026-07-06: Explain Classifier Evidence Without Granting Authority

Decision: Add `delegation explain-policy` for plain-language explanations of
`local.classifier` ledger evidence, including an opt-in Ollama explanation path.

Why: Users should not need to read raw JSON to understand why a gate was
recommended. Better explanation improves experience without weakening the trust
boundary.

Trust boundary:

- deterministic classifier evidence remains the authority for gates
- model explanations are opt-in
- model explanations cannot change `classification`, `recommended_gate`,
  approval evidence, eval results, or promotion decisions

Follow-up: Consider showing these explanations in the future dashboard after
the user approves the visual/interface direction.

## 2026-07-06: Move Public Identity To DelegationHQ

Decision: Move the public package and product identity from Delegation Bot /
`delegation-bot` to DelegationHQ / `delegationhq`.

Why: The project is becoming more than a bot. DelegationHQ keeps the core
delegation idea while making the product feel like a control room for agentic
work, future docs, and possible hosted subscriptions.

Compatibility:

- keep the CLI command as `delegation`
- keep the Python import namespace as `delegation_bot`
- keep existing ledger markers and fixtures compatible
- use `delegationhq` for package metadata, release docs, and future public
  distribution

Decision: Add a user-local Windows installer for `delegation.exe`.

Why: The first-run experience should become easy without forcing users to learn
Python packaging. The installer keeps the path non-admin by copying the built
executable under `%LOCALAPPDATA%\DelegationHQ\bin`, optionally adding the user
PATH, and running `doctor --skip-github` as a smoke check.

Follow-up: Run the build and install scripts on a clean Windows release host
before publishing a public `.exe`.

## 2026-07-07: Add GitHub App Scoped Token Planning

Decision: Add `delegation github-app-plan` for local GitHub App permission and
installation-token planning.

Why: Real users should not need broad personal tokens for live actions. Before
DelegationHQ implements hosted GitHub App auth, maintainers need a concrete,
reviewable plan for read-only, issue-write, and actions-control modes. This
keeps GitHub auth inside the same control-plane loop: plan first, gate later,
record everything.

Guardrails:

- the command does not create a GitHub App
- the command does not mint tokens, call GitHub, or write to repositories
- issue-write and actions-control stay separate modes
- a GitHub App token never bypasses dry-runs, policy gates, confirmation
  tokens, or ledger evidence
- private keys, webhook secrets, and installation tokens stay outside the
  repository

Follow-up: Choose the first hosted implementation target, likely read-only or
issue-write, after the local preview flow feels clear.

## 2026-07-07: Add Gated Feedback Recovery Apply

Decision: Add `delegation apply-feedback` to preview and live-apply feedback
recovery comments to existing GitHub Issues, with optional issue closing behind
a stronger confirmation token.

Why: The feedback loop should not stop at drafting issues. DelegationHQ should
prove that a failure recovered, comment on the same live issue with the
evidence, and optionally close it, while preserving the core rule:
plan first, gate first, ledger proof after.

Guardrails:

- preview mode is the default and never writes to GitHub
- comment-only live apply requires `--apply --confirm LIVE_FEEDBACK_ISSUES`
- issue closing requires `--apply --close --confirm CLOSE_FEEDBACK_ISSUES`
- the command targets only recovery drafts with known live issue numbers
- repository allowlists, approval policy, token gates, and ledger eval gates
  still apply
- live comment and close results append ledger evidence with issue and comment
  URLs when GitHub returns them

Follow-up: Connect this path to the future GitHub App `issue-write` token
provider so users do not need broad personal access tokens.
