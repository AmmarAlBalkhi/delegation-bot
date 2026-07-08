# Demo: Mission Control In 60 Seconds

DelegationHQ is mission control for agentic AI work.

Simple version:

```text
AI proposes.
Bot dry-runs.
Policy gates check risk.
Recorder plans proof.
Ledger keeps receipts.
Evals decide what earns trust.
```

## Run The Demo

From the repository root:

```bash
python scripts/delegation.py demo --control-loop
```

Expected first signal:

```text
Status: ready
RunPrint audit: recorded
```

That one command writes `.delegation/demo.jsonl`, checks the MCP gate, previews
GitHub Actions dispatch, records an Agent Gate receipt, records a local approval
receipt, records an evidence receipt, audits intent against proof, and
runs evals.

Then inspect the result:

```bash
python scripts/delegation.py mission-status --ledger .delegation/demo.jsonl
python scripts/delegation.py agent-packet --ledger .delegation/demo.jsonl --action-id agent_gate.planner.write_issue_draft
```

Simple version:

```text
Agent asks.
DelegationHQ checks.
Human approval is attached.
Recorder proof is attached.
Mission Status says what is next.
Agent Packet gives custom agents a safe job card.
```

## Run The Full Flagship Flow

For the larger example Harnessfile:

```bash
python scripts/delegation.py plan examples/ai-harness-control-plane.yaml --ledger .delegation/demo.jsonl
python scripts/delegation.py ledger .delegation/demo.jsonl --limit 6
python scripts/delegation.py evidence --ledger .delegation/demo.jsonl
python scripts/delegation.py mcp-gate examples/ai-harness-control-plane.yaml --ledger .delegation/demo.jsonl
python scripts/delegation.py apply-actions examples/ai-harness-control-plane.yaml --ledger .delegation/demo.jsonl
python scripts/delegation.py explain-policy --ledger .delegation/demo.jsonl
python scripts/delegation.py eval examples/ai-harness-control-plane.yaml --ledger .delegation/demo.jsonl
```

## The Moment To Show

In both demo paths, the important line is:

```text
Status: ready
```

That proves the mission did not only create a plan. It also declared which MCP
server and tool are allowed, checked the gate, attached approval/proof receipts,
and confirmed the tool risk gate before anything live ran.

After `apply-actions`, the important idea is preview-first execution:

```text
Live dispatch exists, but only after gates pass and the operator explicitly confirms it.
```

That is the product: powerful AI work with visible control before power is used.

## What People Should Notice

- The Harnessfile describes a mission, not one brittle script.
- The plan shows agents, models, workflows, tools, policies, outputs, and evals.
- The ledger records evidence without running live agents or tools.
- The recorder step plans the proof bundle before any evidence capture happens.
- `demo --control-loop` shows the full plan, gate, approval, recording, and
  audit loop in one install-safe command.
- `mission-status` explains the ledger without requiring users to read JSONL.
- `agent-packet` exports a Bring Your Own Agent handoff card.
- `agent-result-ingest` records the custom agent return lane when using the
  handoff flow in [`docs/agent-handoff.md`](agent-handoff.md).
- `evidence` summarizes planned proof bundles without reading raw JSONL.
- `mcp-gate` checks MCP server/tool allowlists and tool risk evidence.
- `apply-actions` previews workflow dispatch by default and can dispatch only with explicit live gates.
- `explain-policy` turns classifier evidence into plain language without giving the model authority.
- Evals explain what passed and what still needs real execution evidence.
- Feedback recovery can preview a GitHub comment or close action only after the
  ledger proves the eval recovered.

## The Product Promise

DelegationHQ should make powerful AI work feel inspectable:

```text
Before the AI does the thing, you can see the thing.
Before proof is captured, you can see what proof is needed.
Before tools run, you can see the power they ask for.
Before trust increases, evidence must pass.
```

## Demo Fixtures

Quick examples:

```bash
python scripts/delegation.py ledger examples/ledgers/github-actions-preview.jsonl --adapter github.actions
python scripts/delegation.py ledger examples/ledgers/mcp-tool-risk.jsonl --adapter mcp.tool
python scripts/delegation.py dashboard examples/ledgers/feedback-recovery.jsonl
python scripts/delegation.py apply-feedback examples/feedback-recovery-harness.yaml --ledger examples/ledgers/feedback-recovery-ready.jsonl
```

These fixtures show the control plane without network calls.

## Start A Real Repo

```bash
python scripts/delegation.py init --goal "prepare this repo for safe AI delegation"
python scripts/delegation.py validate Harnessfile.yaml
python scripts/delegation.py plan Harnessfile.yaml --ledger .delegation/latest.jsonl
```

`init` refuses to overwrite an existing Harnessfile unless you pass `--force`.
