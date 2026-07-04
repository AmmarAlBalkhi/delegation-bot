# Positioning

This document preserves the product framing so the project does not drift while
the implementation grows.

## Core Sentence

```text
Delegation Bot is mission control for agentic work: dry-run AI missions, route
them to any harness, enforce approvals, keep evidence, run evals, and promote
agents only when trust is earned.
```

Shorter version:

```text
Mission control for agentic work.
```

Category:

```text
AI delegation control plane
```

## Plain Meaning

Most tools help agents do work.

Delegation Bot helps humans trust, control, compare, and improve that work
across many agent tools.

Most agent tools start at execution:

```text
Run the agent.
```

Delegation Bot starts one level above:

```text
Should this work happen, who or what can do it, what proof is required, and
does this agent deserve more power next time?
```

## The Loop

The core loop is the product:

```text
Harnessfile -> dry-run plan -> policy gates -> adapter actions -> run ledger -> evals -> promotion
```

Everything we build should strengthen that loop.

## Hybrid Trust Model

Delegation Bot should be AI-enabled, not AI-governed:

```text
AI proposes.
Delegation Bot verifies.
Human approves risky actions.
Ledger records everything.
Evals decide whether trust increases.
```

AI should help draft Harnessfiles, recommend adapters, explain plans, summarize
ledgers, and propose fixes. Deterministic code should still control validation,
policy gates, approval requirements, evidence requirements, ledger writes, eval
results, and promotion readiness.

See `docs/hybrid-trust-model.md` for the full principle.

## What Problems It Solves

1. AI actions are hard to inspect before they happen.
2. Teams use many agent tools at once.
3. There is no shared evidence trail across agent frameworks.
4. Approvals are often scattered across prompts, chats, and memory.
5. Agent mistakes do not automatically become future evals.
6. Agent autonomy is too binary: blocked or trusted.
7. Framework lock-in makes long-term AI operations risky.

## Use Cases

- AI code review mission
- CI repair mission
- weekly engineering planning
- agent comparison across Codex, Claude Code, OpenAI Agents SDK, LangGraph, and
  local tools
- regulated team approval and audit workflow
- consulting or agency playbooks for client AI automation
- open-source maintainer triage and issue planning
- enterprise platform team standard for AI work

## What Is Adjacent

These tools prove the space is real:

- OpenAI Agents SDK, CrewAI, AutoGen, and LangGraph help people build and run
  agents.
- LangSmith, Langfuse, AgentOps, and Braintrust help trace, debug, evaluate,
  and monitor LLM or agent apps.
- MCP standardizes how AI connects to tools and data.
- Claude Code and Codex are powerful execution harnesses.

The ingredients exist. The full recipe is still unusual.

## Why Delegation Bot Can Be Unique

Delegation Bot is not trying to be the best agent runtime, tracing dashboard,
or prompt platform.

It should be the neutral mission-control layer above those tools:

- repo-native Harnessfile
- dry-run plan before action
- policy gates before tools
- adapters for many harnesses
- JSONL run ledger as durable evidence
- evals that judge runs
- feedback issues from failures
- promotion ladder for agent autonomy

The closest threat is a user combining an agent framework with an observability
platform. Our answer is that Delegation Bot owns the planning, approval,
evidence, and promotion layer before and around execution.

## What We Are Not

Do not let the project drift into:

- just another agent framework
- just another tracing dashboard
- just another workflow runner
- just another prompt or eval platform
- a dashboard before the CLI loop is loved
- vague safety claims without ledger evidence

## Marketing Hooks

Use these later for README, launch posts, website copy, and talks:

```text
Plan it once. Dry-run it. Approve it. Execute anywhere. Learn from every run.
```

```text
Give agents more power as they prove themselves.
```

```text
GitHub Actions for AI work, plus Terraform-style planning, plus audit logs,
plus evals, plus adapter portability.
```

```text
The missing control plane above agent frameworks.
```

## Promise To Keep

We stay unique only if we stay focused.

The product is not the number of integrations. The product is the trust loop:
plan, approve, execute, record, evaluate, improve, and promote.
