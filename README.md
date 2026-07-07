# DelegationHQ

DelegationHQ is **mission control for agentic AI work**.

It lets you dry-run AI missions, route them to any harness, enforce approvals,
keep evidence, run evals, and promote agents only when trust is earned.

The big idea is a **harness for AI harnesses**: a repo-native layer above Codex,
Claude Code, Anthropic Claude, OpenAI Agents SDK, LangGraph, MCP tools, GitHub
Actions, local scripts, and human review.

```text
AI proposes.
DelegationHQ verifies.
Human approves risky actions.
Ledger records everything.
Evals decide whether trust increases.
```

The command stays intentionally short:

```bash
delegation demo
delegation plan Harnessfile.yaml --ledger .delegation/latest.jsonl
```

Package/public identity is moving to `delegationhq`. The Python import
namespace remains `delegation_bot` during the compatibility window.

## Quick Start

From a source checkout:

```bash
python -m pip install -e .
delegation demo
```

That runs an install-safe demo: dry-run plan, ledger, MCP tool policy gate,
GitHub Actions preview, and evals. It does not write to GitHub, call a model, or
run an agent.

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
[`docs/demo.md`](docs/demo.md).

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
  `github.actions`, `human.approval`, `openclaw.gateway`, `hermes.agent`, and
  local classifiers.
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
| `delegation demo` | Run the install-safe mission-control demo in one command. |
| `delegation init --goal "goal"` | Create a starter Harnessfile for a repository. |
| `delegation doctor --skip-github` | Check local readiness and show the next useful command. |
| `delegation suggest "goal" --plan --ledger .delegation/run.jsonl` | Draft a Harnessfile from plain language and dry-run it. |
| `delegation plan Harnessfile.yaml --ledger .delegation/run.jsonl` | Compile a Harnessfile into a dry-run ledger. |
| `delegation ledger .delegation/run.jsonl` | Inspect run evidence. |
| `delegation explain-policy --ledger .delegation/run.jsonl` | Explain classifier policy evidence in plain language. |
| `delegation dashboard .delegation/run.jsonl` | Build a read-only mission snapshot for future UI/cockpit work. |
| `delegation mcp-gate Harnessfile.yaml --ledger .delegation/run.jsonl` | Check MCP tool allowlists and risk evidence. |
| `delegation eval Harnessfile.yaml --ledger .delegation/run.jsonl --feedback` | Run evals and draft improvement issues. |
| `delegation recover-feedback Harnessfile.yaml --ledger .delegation/run.jsonl` | Draft recovery updates when previously failing evals pass. |
| `delegation promote Harnessfile.yaml --ledger .delegation/run.jsonl` | Check whether agents can earn more autonomy. |
| `delegation apply-issues Harnessfile.yaml --ledger .delegation/run.jsonl` | Preview live GitHub Issue writes. |
| `delegation apply-actions Harnessfile.yaml --ledger .delegation/run.jsonl` | Preview or live-dispatch gated GitHub Actions workflows. |

Live actions stay behind explicit gates. GitHub Issues require
`--apply --confirm LIVE_GITHUB_ISSUES`; GitHub Actions require
`--apply --confirm LIVE_GITHUB_ACTIONS`. Both need `GITHUB_TOKEN` or `GH_TOKEN`.

## Try Fixtures

Fixtures are tiny ledgers that make the system easier to understand.

```bash
delegation ledger examples/ledgers/adapter-good.jsonl --adapter sample.echo
delegation ledger examples/ledgers/adapter-blocked.jsonl --status blocked
delegation ledger examples/ledgers/github-issue-applied.jsonl --adapter github.issue
delegation ledger examples/ledgers/github-actions-preview.jsonl --adapter github.actions
delegation ledger examples/ledgers/mcp-tool-risk.jsonl --adapter mcp.tool
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
- MCP tool permission and prompt-injection risk evidence
- deterministic local-classifier policy profiles
- `explain-policy` for low-friction classifier explanations that do not grant authority
- no-network and opt-in live model-backed Harnessfile suggestions for OpenAI,
  Anthropic, and Ollama
- package metadata for the `delegationhq` distribution and `delegation` console
  command
- Windows `.exe` build and user-local install scripts for local packaging smoke
  tests

Live agent execution is intentionally not the default yet. The current focus is
trustworthy plans, evidence, adapter portability, feedback loops, and a first
user experience that feels useful quickly.

## Docs Map

Start here:

- [60-second demo](docs/demo.md)
- [Vision](docs/vision.md)
- [Architecture](docs/architecture.md)
- [Positioning](docs/positioning.md)
- [Roadmap](ROADMAP.md)
- [Next actions](docs/next-actions.md)

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
- [Live execution gate](docs/live-execution-gate.md)
- [GitHub Issue apply](docs/github-issue-apply.md)
- [GitHub Actions apply](docs/github-actions-apply.md)
- [MCP tool risk](docs/mcp-tool-risk.md)
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
