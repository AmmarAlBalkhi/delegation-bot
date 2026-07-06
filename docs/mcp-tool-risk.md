# MCP Tool Risk Evidence

`mcp.tool` plans now include permission and prompt-injection risk evidence.

Caveman version:

```text
Tool wants power.
Bot asks what kind.
Bot checks if text can trick it.
Bot writes the risk down.
```

## Why This Exists

MCP is becoming a common way for AI apps to reach tools, data, and workflows.
That is exactly why DelegationHQ should support it carefully.

A tool call can look small but still be powerful:

- reading files
- calling web APIs
- executing commands
- sending messages
- writing issues or code
- passing untrusted text back into an AI model

DelegationHQ should enable those tools, not suppress them, but it should make
their risk visible before execution.

## Evidence

The dry-run `mcp.tool` adapter records:

- `permission_scope`: `read`, `filesystem_read`, `network_read`,
  `write_or_execute`, `network_write`, `secret_access`, or `unknown`
- `risk_level`: `low`, `medium`, or `high`
- `prompt_injection_risk`: `low`, `medium`, or `high`
- `recommended_gate`: `none`, `review_recommended`, or `approval_required`
- `capability_tags`: deterministic tags such as `read`, `filesystem`,
  `network`, `write`, or `secret_access`
- `risk_reasons`: short plain-language reasons

Inspect a normal plan:

```bash
delegation plan examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl
delegation mcp-gate examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl
delegation ledger .delegation/latest.jsonl --adapter mcp.tool
```

Inspect a high-risk fixture:

```bash
delegation ledger examples/ledgers/mcp-tool-risk.jsonl --adapter mcp.tool
```

## Eval

The built-in `mcp_tool_risk_review` eval reads the MCP tool evidence.

It passes when the current dry-run evidence does not require extra review. It
blocks when an MCP tool looks high-risk or needs explicit approval.

This is not a live sandbox. It is the first deterministic trust layer:

```text
adapter writes facts -> eval makes review decision -> human sees next action
```

## MCP Gate

`delegation mcp-gate` is the user-friendly report over the same evidence. It
checks:

- `policies.permissions.allowed_mcp_servers`
- `policies.permissions.allowed_mcp_tools`
- ledger validity
- required adapter evidence
- MCP tool risk review
- approval evidence for high-risk tool plans

If something is blocked, the report names the missing policy list or approval
evidence.

## Current Heuristics

The first classifier is intentionally simple. It looks for:

- write or execute verbs in tool names or argument keys
- network or web indicators
- secret-like argument names
- filesystem path arguments
- prompt-surface fields such as `prompt`, `content`, `html`, `markdown`,
  `message`, `query`, `url`, and `text`
- obvious prompt-injection phrasing such as attempts to ignore or override
  instructions

This gives us a reliable baseline that works without calling a model. Later, a
local classifier or a black-box tool environment can add deeper analysis.

## Sources Checked

Source check date: 2026-07-05.

- [MCP tools specification](https://modelcontextprotocol.io/specification/draft/server/tools)
- [MCP 2025-03-26 tools specification](https://modelcontextprotocol.io/specification/2025-03-26/server/tools)
- [OWASP LLM01 prompt injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
- [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)

## Next

Future work should add:

- explicit MCP server allowlists
- per-tool permission policies
- schema-aware argument validation
- tool result output validation
- local-model risk classification
- optional integration with a hardened tool sandbox or black-box execution
  environment
