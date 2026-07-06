# Adapter Candidate Matrix

Source check date: 2026-07-05.

This matrix helps decide which harness adapters should come next. It should be
updated before public launch and before any major adapter push.

Simple version:

```text
Many agent tools exist.
DelegationHQ should not become all of them.
DelegationHQ should control, verify, and remember work across them.
```

## Selection Rule

Prioritize adapters that strengthen the core loop:

```text
Harnessfile -> dry-run plan -> policy gates -> adapter actions -> run ledger -> evals -> promotion
```

Good adapter candidates have:

- real users or strong ecosystem pull
- clear dry-run surface
- useful evidence to capture
- obvious safety boundary
- low setup friction for contributors
- a path toward live execution later

## Near-Term Priority

| Rank | Candidate | Why It Matters | First Useful Slice | Risk | Source |
| --- | --- | --- | --- | --- | --- |
| 1 | `mcp.tool` | MCP is becoming the common tool/data connector layer for agent apps. | Better server/tool capability evidence, permission scope, and prompt-injection notes. | high | [MCP intro](https://modelcontextprotocol.io/docs/getting-started/intro) |
| 2 | `github.actions` | GitHub Actions is the repo-native execution and CI surface. | Read workflow/job intent, require approval for dispatch, record run URL. | medium | [GitHub Actions docs](https://docs.github.com/actions) |
| 3 | `claude.code` / `anthropic.messages` | Claude Code is a major coding-agent workflow, and Anthropic exposes agent/tool patterns. | Plan coding-agent handoff, capture permission mode, evidence path, and model context. | high | [Claude Code repo](https://github.com/anthropics/claude-code), [Anthropic MCP connector](https://platform.claude.com/docs/en/agents-and-tools/mcp-connector) |
| 4 | `openai.agents` | OpenAI Agents SDK has first-party agent, handoff, tool, guardrail, and tracing concepts. | Map agents, tools, guardrails, handoffs, and trace ids into ledger evidence. | medium | [OpenAI Agents guide](https://developers.openai.com/api/docs/guides/agents), [Agents SDK docs](https://openai.github.io/openai-agents-python/) |
| 5 | `langgraph.graph` | LangGraph is strong where durability, human-in-the-loop, and stateful workflows matter. | Capture graph id, checkpoint id, interrupted state, and resume policy. | medium | [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) |
| 6 | `local.classifier` / `ollama.model` | Local models support privacy-preserving policy checks and low-cost suggestions. | Keep local model suggestions and classifier explanations opt-in and non-authoritative. | medium | [Ollama API](https://docs.ollama.com/api/introduction), [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling) |
| 7 | `crewai.crew` | CrewAI has a popular multi-agent mental model: crews, agents, tasks, flows. | Dry-run crew/task map and expected artifacts. | medium | [CrewAI docs](https://docs.crewai.com/) |
| 8 | `microsoft.agent_framework` | Microsoft is moving AutoGen and Semantic Kernel concepts into a newer Agent Framework. | Track as a successor path for `autogen`-style multi-agent orchestration. | medium | [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/), [AutoGen research](https://www.microsoft.com/en-us/research/project/autogen/) |
| 9 | `linear.issue` / `jira.issue` | Teams live in issue trackers; GitHub Issues will not be enough for companies. | Preview-first issue draft and update evidence. | low | Future enterprise research |
| 10 | `slack.message` | Human approval and visibility often happen in chat. | Draft-only message preview with approval links and ledger references. | high | Future enterprise research |

## What To Build First

Build in this order:

1. Improve adapters already in the repo before adding many new names.
2. Add stronger evidence contracts for `mcp.tool`, `github.actions`,
   `openai.agents`, `anthropic.messages`, `claude.code`, and `langgraph.graph`.
3. Add one new adapter only when it proves a new category: local model,
   multi-agent crew, enterprise tracker, or team chat.
4. Keep every new adapter dry-run first.

## Adapter Scorecard

Score each candidate from 1 to 5 before implementation.

| Field | Meaning |
| --- | --- |
| User pull | How likely real users are to ask for it. |
| Evidence value | How much useful proof the adapter can leave in the ledger. |
| Dry-run clarity | How easy it is to preview without live action. |
| Safety risk | How dangerous live execution could be. Higher score means higher risk. |
| Contributor fit | How easy it is for contributors to add tests and fixtures. |

The first public adapter issues should prefer high user pull, high evidence
value, high dry-run clarity, and medium-or-lower contributor difficulty.

## Important Boundaries

- DelegationHQ should not replace agent frameworks.
- DelegationHQ should not hide tool risk behind friendly wording.
- Live execution must stay behind policy gates and human approval.
- A new adapter is not done until it has a contract, dry-run output, ledger
  evidence, tests, docs, and a fixture.

## Next Implementation Picks

1. Add a dry-run `shell.command` adapter contract before allowing any command
   execution.
2. Run the packaged demo/install path on a clean Windows release host.
3. Add token-scope diagnostics and a dedicated cancel command for
   `github.actions` live dispatch.
4. Add a small `crewai.crew` or Microsoft Agent Framework planning contract
   only after the current adapter docs are easy to follow.
