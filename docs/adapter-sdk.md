# Adapter SDK

The adapter SDK is the plug-in standard for DelegationHQ.

Simple version: an adapter accepts one planned action, returns one result, and
leaves ledger-ready events plus evidence. That is how DelegationHQ can sit
above Codex, Claude Code, OpenAI Agents SDK, LangGraph, MCP tools, GitHub
Actions, local models, and human approval steps without hard-coding each one
into the planner.

## Core Shape

The SDK lives in `delegation_bot/adapter_sdk.py`.

Every adapter should expose:

- `contract`: the adapter contract, including inputs, outputs, risk, approvals,
  planned event types, and required evidence
- `plan(request)`: a dry-run method that returns what the adapter would do

The important dataclasses are:

- `AdapterRequest`: mission id, action id, objective, inputs, metadata, and
  dry-run mode
- `AdapterResult`: status, message, outputs, evidence, and ledger events
- `AdapterEvent`: a ledger-ready event emitted by the adapter

The first implementation is `GitHubIssueDryRunAdapter` in
`delegation_bot/builtin_adapters.py`. The dry-run planner uses SDK-backed
adapter results when an implemented adapter exists.

The contributor-friendly implementation is `SampleEchoDryRunAdapter`. It never
uses the network and exists so adapter authors can copy a complete, low-risk
pattern.

## Why This Matters

Contracts describe the promise.

The SDK tests whether an implementation keeps that promise.

That means future adapters can be added without rewriting the core planner. The
adapter only has to prove:

- it accepts the declared inputs
- it returns the declared outputs
- it emits the declared ledger event types
- it leaves the required evidence
- it clearly reports whether the run is planned, blocked, failed, or complete

## Minimal Example

```python
from delegation_bot.adapter_sdk import AdapterRequest, validate_adapter_result
from delegation_bot.adapters import get_adapter_contract
from delegation_bot.builtin_adapters import get_builtin_adapter

contract = get_adapter_contract("github.issue")
adapter = get_builtin_adapter("github.issue")

request = AdapterRequest(
    adapter_id="github.issue",
    action_id="executor.issue_planner",
    mission_id="ai-harness-control-plane",
    objective="Create a planning issue.",
    inputs={
        "repository": "AmmarAlBalkhi/delegation-bot",
        "issue_title": "Plan the adapter SDK",
        "issue_body": "Define the request, result, ledger events, and evidence.",
    },
)

result = adapter.plan(request)
errors = validate_adapter_result(contract, result)
```

If `errors` is empty, the adapter result satisfies the contract.

The built-in `required_adapter_evidence` eval later checks the same idea from
the run ledger: every SDK-backed adapter result must leave the evidence and
outputs promised by its contract.

## Contributor Rule

A new adapter should start as dry-run only.

Live execution comes later, after the adapter can prove its plan, evidence, and
ledger events. This keeps the core idea strong: plan first, inspect first, then
execute only when policy allows it.

## Current Built-In Implementations

- `github.issue`: dry-run issue creation/update planner with deterministic
  `issue_marker` evidence
- `github.actions`: dry-run workflow planner with workflow run id, run URL, and
  conclusion evidence
- `codex.thread`: dry-run Codex handoff planner with changed-file and QA
  evidence
- `mcp.tool`: dry-run MCP tool-call planner with `tool_name` and
  `tool_result`, permission, risk, and prompt-injection evidence
- `openai.agents`: dry-run OpenAI Agents SDK workflow planner with `trace_id`
  and `final_output` evidence
- `anthropic.messages`: dry-run Anthropic Messages planner with model, usage,
  and final-output evidence
- `claude.code`: dry-run Claude Code handoff planner with changed-file and QA
  evidence
- `langgraph.graph`: dry-run durable graph planner with checkpoint evidence
- `human.approval`: dry-run approval checkpoint planner with approver and
  approval-status evidence
- `openclaw.gateway`: dry-run local assistant gateway planner with channel and
  assistant-result evidence
- `hermes.agent`: dry-run skill-learning agent planner with skill and
  agent-result evidence
- `local.classifier`: dry-run risk classifier with classification evidence
- `sample.echo`: no-network echo adapter with deterministic `echo_hash`
  evidence for contributors

All current built-in adapter contracts now have dry-run implementations. They
are still not live execution adapters.

## Next SDK Moves

1. Add explicit MCP server/tool allowlist policy.
2. Use `github.actions` dispatch previews to design a future live client.
3. Keep live execution behind policy, approval, and eval gates.

See `docs/build-an-adapter.md` for the contributor path.
See `docs/ledger-fixtures.md` for good, blocked, and failed adapter examples.
