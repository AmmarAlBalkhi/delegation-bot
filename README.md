# DelegationHQ

DelegationHQ is **mission control for agentic AI work**.

It lets you dry-run AI missions, route them to any harness, enforce approvals,
keep evidence, run evals, and promote agents only when trust is earned.

The big idea is a **harness for AI harnesses**: a repo-native layer above Codex,
Claude Code, Anthropic Claude, OpenAI Agents SDK, LangGraph, MCP tools, GitHub
Actions, RunPrint evidence recording, local scripts, and human review.

```text
AI proposes.
DelegationHQ verifies.
Human approves risky actions.
Ledger records everything.
Evals decide whether trust increases.
```

The main workflow is intentionally short:

```bash
delegation workspace-init --path . --plan
delegation agent-add hello_agent --workspace . --command "python -c \"print('hello from agent')\"" --capability read.workspace --allowed-data workspace --evidence command_output --force
delegation agent-run hello_agent --workspace . --execute --confirm LOCAL_AGENT_EXECUTION
delegation app-dashboard --workspace . --preview-agent hello_agent
delegation timeline --workspace .
delegation app-export --workspace . --preview-agent hello_agent
```

Package/public identity is moving to `delegationhq`. The Python import
namespace remains `delegation_bot` during the compatibility window.

## Quick Start

From a source checkout:

```bash
python -m pip install -e .
delegation --version
delegation workspace-init --path . --plan
delegation agent-add hello_agent --workspace . --command "python -c \"print('hello from agent')\"" --capability read.workspace --allowed-data workspace --evidence command_output --force
delegation agent-run hello_agent --workspace . --execute --confirm LOCAL_AGENT_EXECUTION
delegation cockpit --workspace .
delegation app-dashboard --workspace . --preview-agent hello_agent
delegation timeline --workspace .
delegation approval-preview hello_agent --workspace .
delegation app-export --workspace . --preview-agent hello_agent
```

That makes the current folder a local AI workspace, registers a command-backed
custom agent, gates it, runs it only after the exact confirmation token, records
evidence, shows a dashboard-ready control view, prints a mission timeline, and
writes a local browser app bundle under `.delegation/cockpit/`. GitHub is not
required.

Simple version:

```text
Agent asks.
DelegationHQ checks.
Human approves.
RunPrint proof is attached.
Mission status says what is next.
Agent packet tells custom agents what they may do.
```

`workspace-init` makes any local folder a DelegationHQ workspace. It writes a
local Harnessfile, agent registry, and optional dry-run ledger under
`.delegation/`. GitHub is optional, not the core.

Add a custom agent without writing YAML:

```bash
delegation agent-add research_agent --workspace . --command "python agents/research_agent.py" --capability read.workspace --allowed-data workspace --evidence command_output
delegation agent-gate --registry .delegation/agents.yaml research_agent --action read.workspace --target workspace
delegation agent-run research_agent --workspace . --execute --confirm LOCAL_AGENT_EXECUTION
```

`app-state` gives the future app and a first-time user one compact health view:
local readiness, release readiness, ledger snapshot, evidence bundles, next
safe action, and guardrails.

`cockpit` is the short local app backend command. It uses the workspace
defaults and prints the same app-ready state without making users remember
internal ledger or registry paths.

`app-dashboard` is the one-screen app brain: workspace state, Agent Passports,
approval preview, command center, timeline, and next safe actions in one bundle.

`timeline` shows the mission in order: plan, gate, approve, execute, record,
eval, feedback, and promotion.

`approval-preview` is the human card: this agent wants this action, here is
what it can touch, here is the risk, here is the approval/evidence needed, here
is prior history for repeated actions, here are optional reviewer notes and
expiration, here are the approve/block/run commands, and here is the safe next
step.

`app-export` writes a local browser cockpit bundle with `dashboard.json`,
`state.json`, `timeline.json`, and approval preview data. `app-serve` serves the
same workspace state at `http://127.0.0.1:8765/` for the future desktop app path.

`agents` shows Agent Passports for built-in Harnessfile agents and custom
Bring Your Own Agent registries.

`agent-gate` answers the practical control question: this agent wants to do
this action on this target, so should DelegationHQ allow, warn, ask for
approval, or block?

`agent-audit` compares the Agent Gate receipt with RunPrint evidence. Simple
version: the guard wrote a receipt, the camera has a proof plan, and the ledger
keeps both together.

`approval-inbox` turns those receipts into simple cards. `approval-decision`
records a local human approve/block receipt without executing anything.

`runprint-ingest` appends external RunPrint recording evidence to the same
ledger. Simple version: the camera receipt lands, and `agent-audit` can say
`recorded`.

`mission-status` is the plain status page in the terminal: plan, gate,
approval, proof, attention, and next command.

`agent-packet` exports a JSON job card for Bring Your Own Agent workflows. It
tells a custom agent its requested work, allowed tools/data, missing approvals,
required evidence, and return contract.

`agent-result-ingest` is the return lane. The custom agent sends back a small
result JSON, DelegationHQ checks it against the packet, and the ledger records
the agent report plus RunPrint evidence.

Want to start your own repo?

```bash
delegation init --goal "prepare this repo for safe AI delegation"
delegation plan Harnessfile.yaml --ledger .delegation/latest.jsonl
```

Want the larger flagship Harnessfile?

```bash
delegation plan examples/ai-harness-control-plane.yaml --ledger .delegation/demo.jsonl
delegation mcp-gate examples/ai-harness-control-plane.yaml --ledger .delegation/demo.jsonl
delegation apply-actions examples/ai-harness-control-plane.yaml --ledger .delegation/demo.jsonl
delegation explain-policy --ledger .delegation/demo.jsonl
```

For a guided version with what to look for, see
[`docs/demo.md`](docs/demo.md). For the no-GitHub folder workflow, see
[`docs/local-first.md`](docs/local-first.md).

## Windows EXE

On Windows, build and install a user-local executable:

```powershell
.\scripts\install-windows-exe.ps1 -Build -InstallDependencies -AddToPath
```

This installs `delegation.exe` under `%LOCALAPPDATA%\DelegationHQ\bin`, runs a
safe `doctor --skip-github` smoke check, and optionally adds that directory to
your user PATH. Open a new terminal, then run:

```powershell
delegation demo
```

See [`docs/windows-exe.md`](docs/windows-exe.md) before publishing any public
`.exe` artifact.

## What It Does

- Compiles a Harnessfile into a dry-run execution plan.
- Routes work through adapter contracts such as `github.issue`, `mcp.tool`,
  `openai.agents`, `anthropic.messages`, `claude.code`, `langgraph.graph`,
  `github.actions`, `runprint.recorder`, `human.approval`,
  `openclaw.gateway`, `hermes.agent`, and local classifiers.
- Writes a run ledger so every plan, adapter result, eval, approval, and future
  live action has evidence.
- Runs evals for duplicate issue markers, missing adapter evidence, risky
  approvals, MCP tool risk, ledger validity, and pull-request readiness.
- Drafts feedback issues from failed evals, then reuses live GitHub issue links
  when the same failure appears again.
- Promotes agents only when ledger evidence and evals show they are ready.

Simple version:

```text
Harnessfile -> dry-run plan -> policy gates -> adapter actions -> run ledger -> evals -> promotion
```

## Why It Matters

Modern AI work is spreading across agents, scripts, model APIs, workflow
engines, and human approvals. The hard part is no longer only "can the agent do
the task?" It is:

- What is the agent about to do?
- Who approved the risky part?
- Which tool or model did it use?
- What evidence proves it happened?
- Did evals pass?
- Should this agent get more autonomy next time?

DelegationHQ is built to answer those questions before AI work becomes a
black box.

## Core Commands

The table uses the packaged `delegation` command. In a source checkout, replace
`delegation` with `python scripts/delegation.py`.

| Command | Purpose |
| --- | --- |
| `delegation --version` | Show the installed DelegationHQ version. |
| `delegation demo` | Run the install-safe mission-control demo in one command. |
| `delegation demo --control-loop` | Show the full plan -> gate -> approve -> record -> audit loop. |
| `delegation workspace-init --path . --plan` | Turn any folder into a no-GitHub DelegationHQ workspace. |
| `delegation workspace-status --path .` | Show local workspace health, registry status, and ledger status. |
| `delegation agent-add AGENT --workspace . --command "python agent.py"` | Register a custom agent passport without hand-editing YAML. |
| `delegation agent-run AGENT --workspace . --execute --confirm LOCAL_AGENT_EXECUTION` | Gate, execute, and record a command-backed custom agent. |
| `delegation mission-status --ledger .delegation/run.jsonl` | Explain one ledger as plan, gate, approval, proof, and next step. |
| `delegation agent-packet --ledger .delegation/run.jsonl --action-id ID` | Export a BYOA packet for a custom agent. |
| `delegation agent-result-ingest --ledger .delegation/run.jsonl --action-id ID --result .delegation/agent-result.json` | Validate a custom agent result and append proof. |
| `delegation app-plan` | Show the first visible Windows EXE app plan without launching a UI. |
| `delegation app-state --workspace .` | Show one read-only app-ready state bundle for the future local cockpit. |
| `delegation cockpit --workspace .` | Show the local cockpit state with workspace defaults. |
| `delegation app-dashboard --workspace . --preview-agent AGENT` | Show the combined local app brain: state, approval preview, timeline, commands. |
| `delegation timeline --workspace .` | Show mission history as plan, gate, approval, execution, proof, eval, feedback, and promotion. |
| `delegation approval-preview AGENT --workspace .` | Show the human approval card for one agent action. |
| `delegation app-export --workspace . --preview-agent AGENT` | Write a local browser cockpit bundle. |
| `delegation app-serve --workspace .` | Serve the local cockpit on `127.0.0.1` for app testing. |
| `delegation agents Harnessfile.yaml --registry examples/agent-passports.yaml` | Show Agent Passports for built-in and custom agents. |
| `delegation agent-gate Harnessfile.yaml AGENT --action ACTION --target TARGET` | Preview allow/warn/approval/block for an agent action. |
| `delegation approval-inbox --ledger .delegation/run.jsonl` | Show simple approval cards from Agent Gate receipts. |
| `delegation approval-decision --ledger .delegation/run.jsonl --action-id ID --decision approve --approver NAME` | Record a local human approve/block receipt. |
| `delegation runprint-ingest --ledger .delegation/run.jsonl --action-id ID --recording-id REC --bundle-id BUNDLE --artifact PATH` | Append external RunPrint recording evidence. |
| `delegation agent-audit --ledger .delegation/run.jsonl` | Compare Agent Gate intent receipts with RunPrint evidence. |
| `delegation init --goal "goal"` | Create a starter Harnessfile for a repository. |
| `delegation doctor --skip-github` | Check local readiness and show the next useful command. |
| `delegation release-check` | Check local alpha release readiness without publishing anything. |
| `delegation suggest "goal" --plan --ledger .delegation/run.jsonl` | Draft a Harnessfile from plain language and dry-run it. |
| `delegation plan Harnessfile.yaml --ledger .delegation/run.jsonl` | Compile a Harnessfile into a dry-run ledger. |
| `delegation ledger .delegation/run.jsonl` | Inspect run evidence. |
| `delegation evidence --ledger .delegation/run.jsonl` | Summarize planned recorder evidence bundles. |
| `delegation explain-policy --ledger .delegation/run.jsonl` | Explain classifier policy evidence in plain language. |
| `delegation dashboard .delegation/run.jsonl` | Build a read-only mission snapshot for future UI/cockpit work. |
| `delegation mcp-gate Harnessfile.yaml --ledger .delegation/run.jsonl` | Check MCP tool allowlists and risk evidence. |
| `delegation eval Harnessfile.yaml --ledger .delegation/run.jsonl --feedback` | Run evals and draft improvement issues. |
| `delegation recover-feedback Harnessfile.yaml --ledger .delegation/run.jsonl` | Draft recovery updates when previously failing evals pass. |
| `delegation promote Harnessfile.yaml --ledger .delegation/run.jsonl` | Check whether agents can earn more autonomy. |
| `delegation apply-issues Harnessfile.yaml --ledger .delegation/run.jsonl` | Preview live GitHub Issue writes. |
| `delegation apply-actions Harnessfile.yaml --ledger .delegation/run.jsonl` | Preview or live-dispatch gated GitHub Actions workflows. |
| `delegation cancel-actions OWNER/REPO RUN_ID` | Preview or live-cancel a GitHub Actions workflow run. |

Live actions stay behind explicit gates. GitHub Issues require
`--apply --confirm LIVE_GITHUB_ISSUES`; GitHub Actions require
`--apply --confirm LIVE_GITHUB_ACTIONS`; GitHub Actions cancellation requires
`--apply --confirm CANCEL_GITHUB_ACTIONS`. Live modes need `GITHUB_TOKEN` or
`GH_TOKEN`.

## Try Fixtures

Fixtures are tiny ledgers that make the system easier to understand.

```bash
delegation ledger examples/ledgers/adapter-good.jsonl --adapter sample.echo
delegation ledger examples/ledgers/adapter-blocked.jsonl --status blocked
delegation ledger examples/ledgers/github-issue-applied.jsonl --adapter github.issue
delegation ledger examples/ledgers/github-actions-preview.jsonl --adapter github.actions
delegation ledger examples/ledgers/mcp-tool-risk.jsonl --adapter mcp.tool
delegation evidence --ledger .delegation/demo.jsonl
delegation ledger examples/ledgers/feedback-issue-memory.jsonl --adapter github.issue
delegation dashboard examples/ledgers/feedback-recovery.jsonl
```

The last fixture shows the feedback loop remembering a live GitHub issue number
so a repeated eval failure updates the existing issue instead of creating noise.

## Current Status

DelegationHQ is pre-release, but the foundation is working:

- Harnessfile validation and dry-run planning
- run ledger generation and inspection
- adapter contracts and SDK-backed dry-run adapters
- playbooks and catalog filtering
- evals, feedback drafts, and promotion reports
- preview-first live GitHub Issue apply
- preview-first, gated live GitHub Actions dispatch with workflow preflight
- dry-run RunPrint recorder evidence bundle planning
- Agent Gate receipts and `agent-audit` for intent-vs-evidence checks
- `approval-inbox` and `approval-decision` for simple human review receipts
- `runprint-ingest` for attaching external RunPrint recording evidence to a gate receipt
- `demo --control-loop` for the full plan, gate, approval, recording, audit,
  mission-status, and agent-packet path
- `mission-status` for plain terminal status over one ledger
- `agent-packet` for Bring Your Own Agent handoff JSON
- `agent-result-ingest` for validating custom agent results against packets
- MCP tool permission and prompt-injection risk evidence
- deterministic local-classifier policy profiles
- `explain-policy` for low-friction classifier explanations that do not grant authority
- no-network and opt-in live model-backed Harnessfile suggestions for OpenAI,
  Anthropic, and Ollama
- package metadata for the `delegationhq` distribution and `delegation` console
  command
- Windows `.exe` build and user-local install scripts for local packaging smoke
  tests
- `app-state` as a single read-only state bundle for the future local cockpit
- Agent Passport registry reporting for Harnessfile agents and custom BYOA
  agents

Live agent execution is intentionally not the default yet. The current focus is
trustworthy plans, evidence, adapter portability, feedback loops, and a first
user experience that feels useful quickly.

## Docs Map

Start here:

- [60-second demo](docs/demo.md)
- [Control loop](docs/control-loop.md)
- [Vision](docs/vision.md)
- [Architecture](docs/architecture.md)
- [Positioning](docs/positioning.md)
- [Roadmap](ROADMAP.md)
- [Next actions](docs/next-actions.md)
- [Local app shell](docs/local-app.md)
- [App dashboard](docs/app-dashboard.md)
- [Mission timeline](docs/mission-timeline.md)

Build here:

- [Adapter contracts](docs/adapter-contracts.md)
- [Adapter SDK](docs/adapter-sdk.md)
- [Build an adapter](docs/build-an-adapter.md)
- [Adapter compatibility](docs/adapter-compatibility.md)
- [Adapter candidate matrix](docs/adapter-candidate-matrix.md)
- [Playbooks](docs/playbooks.md)

Trust and operations:

- [Hybrid trust model](docs/hybrid-trust-model.md)
- [Agent enablement](docs/agent-enablement.md)
- [Agent Gate](docs/agent-gate.md)
- [Approval Inbox](docs/approval-inbox.md)
- [Live execution gate](docs/live-execution-gate.md)
- [GitHub Issue apply](docs/github-issue-apply.md)
- [GitHub Actions apply](docs/github-actions-apply.md)
- [MCP tool risk](docs/mcp-tool-risk.md)
- [RunPrint recorder boundary](docs/runprint-recorder.md)
- [Local classifier policy](docs/local-classifier-policy.md)
- [Eval-to-issue feedback](docs/eval-to-issue-feedback.md)
- [Ledger viewer](docs/ledger-viewer.md)
- [Ledger fixtures](docs/ledger-fixtures.md)
- [Dashboard data model](docs/dashboard-data-model.md)
- [OpenTelemetry mapping](docs/opentelemetry-mapping.md)

Launch readiness:

- [QA and backup discipline](docs/qa.md)
- [Release checklist](docs/release.md)
- [Windows EXE install](docs/windows-exe.md)
- [Windows EXE app plan](docs/windows-app-plan.md)
- [Brand transition](docs/brand-transition.md)
- [TestPyPI dry run](docs/testpypi-dry-run.md)
- [Open-core strategy](docs/open-core-strategy.md)
- [Contributor license policy](docs/contributor-license-policy.md)

## Contributing

Good first contributions are adapters, eval tests, playbooks, docs examples, and
small ledger fixtures. Start with [CONTRIBUTING.md](CONTRIBUTING.md),
[docs/issue-labels.md](docs/issue-labels.md), and
[docs/public-roadmap-issues.md](docs/public-roadmap-issues.md).

Run local QA before opening a pull request:

```bash
python scripts/qa.py
```

Create a backup before substantial edits:

```bash
python scripts/backup_repo.py
```

## Legacy Compatibility

The original recurring Markdown task bot still exists for older `tasks/*.md`
users, but it is no longer the main product path. New users should start with
Harnessfiles, ledgers, adapters, evals, and playbooks.

Legacy examples live in
[examples/legacy-recurring-tasks](examples/legacy-recurring-tasks/README.md).

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
