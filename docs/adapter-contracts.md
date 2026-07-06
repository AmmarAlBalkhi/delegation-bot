# Adapter Contracts

Adapter contracts are the socket shape for external execution systems.

Simple version: before Delegation Bot talks to Codex, Claude/Anthropic, GitHub
Actions, MCP, OpenAI Agents SDK, LangGraph, OpenClaw, Hermes-style agents, or a
human approver, it should know what that adapter expects, what it can return,
what risk level it carries, and what evidence must appear in the run ledger.

This is the foundation for becoming a harness for AI harnesses.

## Why This Matters

Without contracts, every integration becomes a special case.

With contracts:

- the planner can explain risk before execution
- policy can require approvals consistently
- evals can check whether required evidence exists
- contributors can add adapters without rewriting the core
- users can compare runs across different agent frameworks

## Current Shape

Each adapter contract declares:

- `id`: stable adapter id, such as `codex.thread`
- `kind`: broad family, such as `ai_harness`, `model_provider`, `workflow`,
  `tool`, `ml_model`, or `human`
- `description`: what the adapter is for
- `risk`: `low`, `medium`, or `high`
- `approval_required_for`: policy approval names that can gate the adapter
- `inputs`: information the adapter needs
- `outputs`: artifacts or evidence it can produce
- `planned_event_types`: ledger event types expected during planning
- `required_evidence`: proof that later evals should be able to inspect

The schema lives in `schemas/adapter-contract.v1.schema.json`.

The implementation SDK lives in `delegation_bot/adapter_sdk.py`. See
`docs/adapter-sdk.md` for the adapter author path.

## CLI

List built-in contracts:

```bash
python scripts/delegation.py adapters
```

Inspect one contract:

```bash
python scripts/delegation.py adapters codex.thread --json
```

Compile a plan and see contracts attached to executor actions:

```bash
python scripts/delegation.py plan examples/ai-harness-control-plane.yaml --json
```

When a dry-run ledger is written, executor actions with an adapter contract also
emit the contract's `planned_event_types`. This means the ledger can show both
the generic dry-run action and the adapter-specific events that a live run would
need to satisfy.

## Built-In Contracts

The first built-in contracts are intentionally planning contracts, not live
execution adapters:

- `github.issue`
- `github.actions`
- `sample.echo`
- `codex.thread`
- `openai.agents`
- `anthropic.messages`
- `claude.code`
- `langgraph.graph`
- `mcp.tool`
- `openclaw.gateway`
- `hermes.agent`
- `local.classifier`
- `human.approval`

`openclaw.gateway` and `hermes.agent` are compatibility targets. They tell the
planner how to think about those classes of agents, and now have dry-run
implementations. They are not live integrations yet.

`github.actions` now includes `workflow_run_url` evidence and has a preview-first
live gate through `delegation apply-actions`. Dispatch requires explicit
confirmation, token evidence, repository policy, ledger evidence, and approval
evidence when policy requires it.

`mcp.tool` now includes `permission_scope`, `risk_level`, and
`prompt_injection_risk` evidence so tool calls can be reviewed before any live
tool invocation.

`local.classifier` now includes deterministic `policy_profile` and
`recommended_gate` evidence so local risk review can help users without letting
AI approve itself.

## Design Notes

Good adapter contracts should be boring and precise.

They should answer:

- What do you need before you can run?
- What could go wrong?
- What approval do you need?
- What event will you write?
- What proof will you leave behind?

This matches how modern agentic systems are evolving:

- OpenAI Agents SDK treats tools as structured callable capabilities.
- Anthropic Claude's Messages API supports model calls with structured tool use,
  and Claude Code is an agentic coding harness with CLI, IDE, web, MCP, and
  automation surfaces.
- MCP standardizes tool names, input schemas, and tool results.
- GitHub Actions exposes reusable workflows as automation units.
- LangGraph emphasizes persistent state and checkpoints for durable agent runs.

Delegation Bot sits above these systems. It should not replace them. It should
make their work plannable, reviewable, comparable, and learnable.

## Next Step

The adapter SDK now exists, the dry-run planner uses SDK-backed adapter results,
the ledger viewer can inspect that evidence, and `required_adapter_evidence` can
judge it. Dry-run adapters now exist for every built-in contract.

The next implementation steps are to expand usage around those adapters:

1. use `github.actions` dispatch previews to design a future live client
2. add local-model explanations for classifier recommendations without making
   the model authoritative
3. add clean release-host evidence for the Windows executable path
4. keep live execution behind policy, approval, and eval gates
