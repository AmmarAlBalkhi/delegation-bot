# Vision: A Harness For AI Harnesses

## Thesis

DelegationHQ should evolve from a task-to-issue bot into a control plane for
delegated intelligence.

The world is moving from single AI calls to long-running work systems: agents,
tool servers, workflow engines, code assistants, evaluators, and human approval
loops. Each harness is useful, but teams still need one durable place to answer:

- What is the objective?
- Who or what is allowed to act?
- Which context was available?
- Which tools were exposed?
- Which policies constrained the run?
- What evidence proves the result?
- What should improve next time?

That is the layer this project can own.

## Product Idea

DelegationHQ becomes the repo-native operating layer above AI harnesses.

It does not need to replace OpenAI Agents SDK, Anthropic Claude, Claude Code,
LangGraph, GitHub Actions, MCP, or custom scripts. It should coordinate them
through manifests, adapters, policies, and run ledgers.

The central primitive is:

```text
Delegation = objective + context + executor + policy + evidence + feedback
```

Every run should be reproducible enough to inspect, safe enough to approve, and
structured enough to improve.

The operating principle is hybrid:

```text
AI proposes.
DelegationHQ verifies.
Human approves risky actions.
Ledger records everything.
Evals decide whether trust increases.
```

That means AI can draft, explain, summarize, compare, and execute through
adapters, but the control plane owns validation, policy, evidence, evals, and
promotion.

## What Makes It Different

Most agent frameworks optimize execution. This project should optimize
delegation.

Execution asks: "Can an agent do the task?"

Delegation asks:

- Should this task exist?
- Who is accountable?
- What is the allowed blast radius?
- Which harness is best for this kind of work?
- What proof is required before completion?
- Which failures should become future evals?
- Which repeated patterns should become reusable playbooks?

That is a more durable surface than any single model or framework.

## North Star

The repository should eventually support a `Harnessfile` that can describe a
mission like this:

```yaml
version: delegation.ai/v1
id: weekly-engineering-review
objective: Review open issues, assign next actions, run checks, and draft PRs.
executors:
  - id: planner
    kind: ai_harness
    adapter: openai.agents
  - id: implementer
    kind: ai_harness
    adapter: codex.thread
  - id: verifier
    kind: workflow
    adapter: github.actions
policies:
  approvals:
    required_for: [push, pull_request, external_message]
  budgets:
    max_usd: 10
outputs:
  - github.issue
  - github.pull_request
  - run_ledger
evals:
  - no_unassigned_blockers
  - tests_must_pass
```

The bot should compile that declaration into concrete GitHub Issues, agent runs,
approval prompts, checklists, traces, and improvement tasks.

The Harnessfile should also let users declare agent passports and capability
packs. That means AI systems can gain more autonomy as they prove themselves,
instead of being either fully blocked or fully trusted.

## Strategic Pillars

1. Repo-native truth

   Plans, policies, evals, and playbooks live as versioned files. Git history is
   the governance layer.

2. Harness portability

   Users should be able to route a mission to OpenAI Agents SDK, Anthropic
   Claude, Claude Code, LangGraph, GitHub Actions, shell scripts, or future
   harnesses through adapters.

3. Policy before autonomy

   Permissions, budgets, secret handling, and approval gates should be declared
   before execution.

4. Evidence-first completion

   A task is not done because an agent says it is done. It is done when the
   required artifacts, checks, links, screenshots, traces, or reviews exist.

5. Evals from reality

   Failures and review comments should become regression evals. The system
   should learn structurally, not just conversationally.

6. Human command, machine leverage

   The tool should amplify human judgment. Risky operations should be visible,
   inspectable, and interruptible.

7. Enablement over suppression

   The project should help agents become more useful. Autonomy should increase
   through evidence, evals, ledgers, and clear capability grants.

8. Low-friction trust

   The tool should make trustworthy AI work easier, not heavier. Users should
   get value from a playbook or AI-drafted Harnessfile before they need to learn
   the full schema.

## External Alignment

- OpenAI Agents SDK exposes concepts around orchestration, guardrails, state,
  observability, and evaluation.
- Anthropic Claude exposes model and tool-use surfaces through the Messages API,
  while Claude Code is an agentic coding harness that can work across CLI, IDE,
  web, MCP, and automation workflows.
- MCP standardizes how models discover and invoke tools, while emphasizing
  human visibility and confirmation for tool use.
- LangGraph highlights durable, stateful, long-running agent workflows.
- OpenTelemetry gives a standard mental model for traces, spans, and the path of
  work through a system.

The opportunity is to treat those as execution substrates and make DelegationHQ
the coordination layer above them.

## First Buildable Milestone

The next version should introduce a manifest-first flow:

1. Validate a `Harnessfile`.
2. Compile it into planned GitHub Issues and run steps.
3. Execute in dry-run mode with a structured run ledger.
4. Add adapters one by one, starting with the existing GitHub Issue adapter.
5. Add eval declarations that can pass or fail a run.

This keeps the project small while pointing it toward a much larger product.

## Adoption Frame

The ambition is broad adoption, but popularity is the result, not the method.
The method is to build the most trustworthy public vocabulary for AI delegation:

- a Harnessfile people can read and share
- a dry-run plan people can understand
- a run ledger people can audit
- evals people can extend
- adapters people can contribute
- agents people can safely promote

See `ROADMAP.md` and `docs/adoption-strategy.md` for the adoption plan.
