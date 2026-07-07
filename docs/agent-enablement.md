# Agent Enablement

This project should not be an AI brake pedal. It should be a gearbox.

The goal is to let agents do more valuable work over time while keeping their
powers visible, reviewable, and earned.

## Simple Idea

Agents should have:

- an identity
- a runtime
- a model
- a current autonomy level
- capability packs
- promotion rules
- evidence from previous runs

This turns an agent from "a model with tools" into a teammate with a clear job.

## Autonomy Ladder

Use these levels in Harnessfiles:

```text
suggest -> draft -> act -> operate -> deploy
```

- `suggest`: can recommend what to do
- `draft`: can produce files, plans, comments, or PR drafts
- `act`: can perform approved actions in a limited area
- `operate`: can run recurring workflows with policy gates
- `deploy`: can affect production-like surfaces, always with strict evidence

The ladder is meant to enable more autonomy, not suppress it. Each step should
be earned through evals, approval history, and clean ledgers.

The trust boundary is simple: AI can suggest the next level, but evals and
ledger evidence decide whether the agent actually earns it.

## Agent Passport

An agent passport declares who the agent is and what kind of work it can do.

```yaml
agents:
  - id: implementer
    runtime: codex.thread
    model: planner_model
    autonomy_level: draft
    capability_packs:
      - repo_reader
      - pull_request_drafter
```

This lets the planner say: "Here is the agent, here is its model, here are its
powers, here is what it may do today."

Inspect Harnessfile passports:

```bash
python scripts/delegation.py agents examples/ai-harness-control-plane.yaml
```

## Bring Your Own Agent Registry

Custom agents can also be registered outside the Harnessfile:

```bash
python scripts/delegation.py agents --registry examples/agent-passports.yaml
```

A registry entry can describe a LangGraph agent, CRM/RAG agent, coding agent,
CLI command, MCP workflow, API/webhook agent, or local tool:

```yaml
version: delegation.agent-registry/v1
agents:
  - id: crm_update_agent
    runtime_type: langgraph.graph
    endpoint:
      type: command
      value: python agents/crm_update_agent.py
    autonomy_level: draft
    risk_level: medium
    capabilities:
      - read.crm_accounts
      - draft.crm_updates
    allowed_tools:
      - crm.search
      - crm.draft_update
    allowed_data:
      - crm.accounts
      - sales_notes
    required_approvals:
      - crm.write
    expected_outputs:
      - crm.update_draft
      - run_ledger
    evidence_requirements:
      - run_ledger
      - crm_diff_summary
      - human_confirmation
    promotion_evals:
      - crm_updates_need_confirmation
```

Simple rule:

```text
The custom agent does the work.
DelegationHQ controls the mission, powers, approvals, evidence, evals, and autonomy.
```

The registry schema is `schemas/agent-registry.v1.schema.json`.

## Agent Gate

The next control step is Agent Gate.

```text
Passport = ID card.
Gate = guard at the door.
```

The gate should answer:

- who is the agent?
- what does it want to do?
- what can it touch?
- what is blocked?
- what needs human approval?
- what evidence must be recorded?
- what evals decide whether it did well?

The first command guide is in `docs/agent-gate.md`.

## Capability Packs

Capability packs are reusable bundles of powers.

```yaml
capability_packs:
  - id: pull_request_drafter
    description: Draft code changes and pull requests, but require approval before publishing.
    capabilities:
      - write.working_tree
      - write.pull_request_draft
      - read.test_results
    approval_required_for:
      - publish.pull_request
```

This is better than vague broad access. You can say exactly what kind of power
the agent has.

## Where Other Agents Fit

DelegationHQ should not replace agent runtimes. It should manage them.

- OpenClaw can be a personal assistant runtime.
- Hermes-style agents can be skill-learning executors.
- Codex can be a code implementation executor.
- Claude Code can be a code review or implementation executor.
- OpenAI Agents SDK can run agent teams.
- Anthropic Claude through the Messages API can be a model provider with tool
  use.
- LangGraph can run durable workflows.
- MCP tools can expose external actions.

DelegationHQ sits above them and answers:

- which agent is assigned
- what powers it has
- what model it uses
- what approval gates apply
- what evidence is required
- what happened in the ledger
- whether it earned more autonomy

## Promotion

Agents should earn more power through proof.

```yaml
promotion:
  next_level: act
  requires_evals:
    - approvals_before_risky_actions
    - tests_pass_before_pr
```

This is how we enable AI safely: not by keeping it weak, but by giving it a path
to become trusted.

## Promotion Evaluation

The promotion evaluator reads:

- the Harnessfile agent promotion rules
- a run ledger
- eval result events marked as `passed`

Then it reports whether each agent is ready for the next autonomy level.

Generate eval result events first:

```bash
python scripts/delegation.py eval examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl --write
```

```bash
python scripts/delegation.py promote examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl
```

Simple rule:

```text
an agent is ready only when every required eval has passed evidence in the ledger
```

Dry-run ledgers usually block promotion because they only show planned evals.
That is correct. Agents should not be promoted based on planned checks.

The first built-in evals are:

- `ledger_is_valid`
- `no_duplicate_issue_markers`
- `approvals_before_risky_actions`
- `tests_pass_before_pr`

## First Implementation

The current planner can read:

- `models`
- `capability_packs`
- `agents`
- `executors`
- `policies`
- `evals`

And it emits dry-run actions for:

- model configuration
- capability pack registration
- agent passport preparation
- executor preparation
- policy gates
- outputs
- evals

No live writes happen during planning.

The current CLI can also produce a promotion report. It does not upgrade agents
automatically.
