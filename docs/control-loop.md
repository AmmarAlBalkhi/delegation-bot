# Control Loop

DelegationHQ is the control layer above agents.

Simple version:

```text
plan -> gate -> approve -> record -> audit -> eval -> promote
```

The first visible slice is now:

```bash
delegation demo --control-loop
delegation mission-status --ledger .delegation/demo.jsonl
delegation agent-packet --ledger .delegation/demo.jsonl --action-id agent_gate.planner.write_issue_draft
```

## What Happens

`delegation demo --control-loop` writes one local ledger that shows the product
shape without calling live services:

- a Harnessfile compiles into a dry-run plan
- Agent Gate records what an agent wants to do
- a local human approval receipt is attached when required
- RunPrint recording evidence is attached to the same action id
- Agent audit compares intent with proof and reaches `recorded`
- Mission Status explains the ledger in plain language
- Agent Packet exports a Bring Your Own Agent handoff card

No GitHub write, model call, agent execution, workflow dispatch, or file capture
happens in this demo.

## Why This Matters

Agent Passports are useful, but a passport alone is only an ID card.

The control loop makes the passport practical:

```text
Agent wants power.
DelegationHQ checks if that power is allowed.
Human approves risky work.
RunPrint records what happened.
Evals decide if trust can increase.
```

This is the core product. Everything else should strengthen or simplify this
loop.

## Mission Status

`mission-status` is the operator view:

```bash
delegation mission-status --ledger .delegation/demo.jsonl
```

It answers:

- is there a plan?
- did an agent request an action?
- is approval missing?
- is RunPrint proof planned or recorded?
- what should the user do next?

The output is intentionally plain. Users should not need to understand raw JSONL
to know whether a mission is safe to continue.

## Agent Packet

`agent-packet` is the Bring Your Own Agent bridge:

```bash
delegation agent-packet --ledger .delegation/demo.jsonl \
  --action-id agent_gate.planner.write_issue_draft \
  --output .delegation/agent-packet.json
```

The packet tells an outside agent:

- who it is
- what runtime it uses
- what action it may perform
- what tools and data it may touch
- what approvals and evidence are required
- what it must return
- what it must not do

This keeps DelegationHQ provider-neutral. A LangGraph agent, Codex thread,
Claude Code workflow, CRM agent, MCP workflow, local CLI tool, or webhook agent
can receive the same kind of job card.

## Product Rule

Do not make users configure the whole machine before they feel value.

The first experience should be:

```text
run demo -> see control -> understand next move
```

Advanced rules can exist underneath, but the user-facing loop should stay short:

```text
add agent -> give mission -> preview risk -> approve/block -> record evidence -> review result -> earn trust
```
