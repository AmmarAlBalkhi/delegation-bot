# Adapter Compatibility Matrix

Delegation Bot is a neutral layer above many AI and automation harnesses.

Simple version: adapters let one Harnessfile plan work across different tools
without making the project depend on one agent framework.

## Status Labels

- `contract`: the adapter has a declared input, output, risk, approval, and
  evidence shape
- `dry-run`: the adapter can produce local ledger evidence without live calls
- `preview-gate`: the adapter has a command that checks policy and evidence
  before any future live action
- `policy-gate`: the adapter has explicit policy checks that produce a user
  report
- `live-gate`: live execution is designed, gated, and intentionally limited
- `live`: live execution exists

## Current Matrix

| Adapter | Family | Status | Current Use | Required Evidence |
| --- | --- | --- | --- | --- |
| `github.issue` | workflow | dry-run, live-gate | Plan or gated-apply GitHub issue creation or updates | `issue_marker` |
| `github.actions` | workflow | dry-run, preview-gate | Plan workflow verification and gated dispatch preview | `workflow_run_id`, `workflow_run_url`, `conclusion` |
| `sample.echo` | tool | dry-run | No-network contributor example and fixture source | `echo_hash` |
| `codex.thread` | AI harness | dry-run | Plan Codex coding-agent handoff | `changed_files`, `qa_result` |
| `openai.agents` | AI harness | dry-run | Plan OpenAI Agents SDK workflow | `trace_id`, `final_output` |
| `anthropic.messages` | model provider | dry-run | Plan Claude Messages API call | `model`, `usage`, `final_output` |
| `claude.code` | AI harness | dry-run | Plan Claude Code handoff | `changed_files`, `qa_result` |
| `langgraph.graph` | workflow | dry-run | Plan durable graph workflow and checkpoint | `checkpoint_id` |
| `mcp.tool` | tool | dry-run, risk-eval, policy-gate | Plan MCP tool call with allowlist, permission, and prompt-injection risk evidence | `tool_name`, `tool_result`, `permission_scope`, `risk_level`, `prompt_injection_risk` |
| `openclaw.gateway` | AI harness | dry-run | Plan local assistant gateway handoff | `channel`, `assistant_result` |
| `hermes.agent` | AI harness | dry-run | Plan skill-learning agent step | `skill_id`, `agent_result` |
| `local.classifier` | ML model | dry-run, policy-profile | Plan local risk classification with deterministic profile evidence | `classification`, `policy_profile`, `recommended_gate` |
| `human.approval` | human | dry-run | Plan human approval checkpoint | `approver`, `approval_status` |

No built-in adapter has unrestricted live execution. That is intentional.

## Why This Matters

The matrix lets users answer:

- which harnesses can I plan today?
- which ones leave evidence in the ledger?
- which ones need approvals?
- which ones are only compatibility targets?
- where can contributors help next?

## Compatibility Promise

The Harnessfile should stay stable even when the underlying agent world changes.

That means:

- an OpenAI Agents mission should be comparable to a Claude Code mission
- a Codex handoff should leave evidence in the same ledger shape as a LangGraph
  or GitHub Actions step
- a future live adapter should start by satisfying the dry-run contract
- users should be able to change adapter backends without rewriting the whole
  mission

## Adapter Families

### AI Harnesses

Examples:

- `codex.thread`
- `openai.agents`
- `claude.code`
- `openclaw.gateway`
- `hermes.agent`

These are the most powerful adapters and should stay behind approval gates until
the dry-run evidence, permissions, and evals are strong.

### Model Providers

Examples:

- `anthropic.messages`

Model providers should expose model, usage, final output, and tool-call
evidence without assuming they own the whole mission.

### Workflows

Examples:

- `github.issue`
- `github.actions`
- `langgraph.graph`

Workflow adapters coordinate visible work, verification, or durable state.

### Tools

Examples:

- `mcp.tool`
- `sample.echo`

Tool adapters should be narrow, explicit, and easy to test.

### Humans

Examples:

- `human.approval`

Human approval is a first-class adapter because approval is part of the mission,
not a side conversation.

## Next Compatibility Work

1. Use the `github.actions` preview gate as the design base for a future live
   dispatch client.
2. Add local-model explanations for classifier recommendations without making
   the model authoritative.
3. Run executable packaging on a clean release host and record evidence.
4. Add contribution labels for adapter requests.
5. Add a compatibility badge once live-gated adapters exist.
