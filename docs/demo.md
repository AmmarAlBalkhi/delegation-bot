# Demo: Mission Control In 60 Seconds

Delegation Bot is mission control for agentic AI work.

Simple version:

```text
AI proposes.
Bot dry-runs.
Policy gates check risk.
Ledger keeps proof.
Evals decide what earns trust.
```

## Run The Demo

From the repository root:

```bash
python scripts/delegation.py doctor --skip-github
python scripts/delegation.py plan examples/ai-harness-control-plane.yaml --ledger .delegation/demo.jsonl
python scripts/delegation.py ledger .delegation/demo.jsonl --limit 6
python scripts/delegation.py mcp-gate examples/ai-harness-control-plane.yaml --ledger .delegation/demo.jsonl
python scripts/delegation.py apply-actions examples/ai-harness-control-plane.yaml --ledger .delegation/demo.jsonl
python scripts/delegation.py eval examples/ai-harness-control-plane.yaml --ledger .delegation/demo.jsonl
```

## The Moment To Show

After `mcp-gate`, the important line is:

```text
Status: ready
```

That proves the Harnessfile did not only create a plan. It also declared which
MCP server and tool are allowed, checked the ledger evidence, and confirmed the
tool risk gate before anything live ran.

After `apply-actions`, the important idea is preview-first execution:

```text
Live dispatch stays locked until the operator explicitly confirms it.
```

That is the product: powerful AI work with visible control before power is used.

## What People Should Notice

- The Harnessfile describes a mission, not one brittle script.
- The plan shows agents, models, workflows, tools, policies, outputs, and evals.
- The ledger records evidence without running live agents or tools.
- `mcp-gate` checks MCP server/tool allowlists and tool risk evidence.
- `apply-actions` previews workflow dispatch but keeps live dispatch locked.
- Evals explain what passed and what still needs real execution evidence.

## The Product Promise

Delegation Bot should make powerful AI work feel inspectable:

```text
Before the AI does the thing, you can see the thing.
Before tools run, you can see the power they ask for.
Before trust increases, evidence must pass.
```

## Demo Fixtures

Quick examples:

```bash
python scripts/delegation.py ledger examples/ledgers/github-actions-preview.jsonl --adapter github.actions
python scripts/delegation.py ledger examples/ledgers/mcp-tool-risk.jsonl --adapter mcp.tool
python scripts/delegation.py dashboard examples/ledgers/feedback-recovery.jsonl
```

These fixtures show the control plane without network calls.
