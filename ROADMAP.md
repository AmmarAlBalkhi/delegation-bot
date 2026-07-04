# Roadmap: The Million-Star Plan

This project should not chase stars as a vanity metric. Stars matter because
GitHub uses them for appreciation, recall, discovery, and popularity signals.
The real target is trust at massive scale: a tool developers keep, share, and
use because it makes AI work safer and more legible.

## One-Sentence Product

Delegation Bot is the mission control layer for AI work: write one Harnessfile,
dry-run the plan, route work to any agent harness, enforce policy, and get an
auditable run ledger with evals.

It should enable agents, not suppress them. The project gives agents an autonomy
ladder: suggest, draft, act, operate, deploy.

The trust model is hybrid:

```text
AI proposes.
Delegation Bot verifies.
Human approves risky actions.
Ledger records everything.
Evals decide whether trust increases.
```

The experience promise is equally important: useful in 60 seconds, powerful
after 10 minutes, and deep only when the user asks for depth.

## The Wedge

Start with the problem every serious AI builder already feels:

> "My agents can act, but I cannot reliably see, approve, replay, compare, or
> improve what they did across tools and frameworks."

The first lovable product is not a universal agent runtime. It is the thing that
wraps agent runtimes with plans, approvals, evidence, and learning loops.

## Milestones

### 0. Trustable Dry Run

Goal: A developer can point the CLI at a Harnessfile and see exactly what would
happen before anything writes to GitHub or calls an agent.

Deliverables:

- compile Harnessfile into an execution plan
- explain planned actions in human-readable text
- write a dry-run ledger
- fail clearly on invalid policy or missing evidence requirements
- show agent passports, capability packs, models, and autonomy levels before run

Current command shape:

```bash
python scripts/delegation.py plan examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl
```

### 1. GitHub-Native Control Plane

Goal: A repository can run Delegation Bot as a GitHub Action and use Issues as
the visible coordination surface.

Deliverables:

- GitHub Issue adapter
- checklist and backlink generation
- run ledger artifact
- policy gates for risky actions
- issue templates for bugs, adapters, evals, and playbooks

### 2. Adapter SDK

Goal: Contributors can add new harness adapters without touching the core.

Deliverables:

- adapter interface
- adapter contract registry
- adapter contract schema
- adapter contract CLI
- adapter test contract
- example adapters for GitHub Actions, Codex threads, Claude Code, MCP tools,
  and shell
- docs for building a new adapter in under 30 minutes

### 2.5 Agent Enablement Layer

Goal: Agents can earn more power over time through visible evidence.

Deliverables:

- agent passports
- autonomy ladder
- capability packs
- promotion rules based on evals and ledger evidence
- promotion reports that show ready vs blocked agents
- compatibility notes for OpenClaw, Hermes-style agents, Codex, Claude Code,
  Anthropic Claude, OpenAI Agents SDK, LangGraph, CrewAI, AutoGen, and MCP tools

### 3. Evals From Reality

Goal: Every failed run can become a regression test or improvement issue.

Deliverables:

- eval declaration format
- built-in evals for duplicates, missing evidence, approvals, and failed tests
- eval report output
- eval result events written back to the run ledger
- failure-to-issue feedback loop

### 4. Playbook Marketplace

Goal: Teams can share reusable Harnessfiles for common AI work.

Deliverables:

- `playbooks/` convention
- starter playbooks for code review, weekly planning, release readiness,
  documentation refresh, and CI repair
- contribution guidelines for playbooks
- compatibility metadata for adapters and policies

### 5. AgentOps Standard Library

Goal: Delegation Bot becomes the default open-source vocabulary for trustworthy
AI delegation.

Deliverables:

- stable Harnessfile v1
- stable run ledger event schema
- stable adapter contract
- OpenTelemetry mapping
- MCP-facing tool surface
- governance process for schema evolution

### 6. Public Package And Release Trust

Goal: Other users can install the project confidently and understand its legal
and release posture.

Deliverables:

- `pyproject.toml`
- `delegation_bot` package namespace
- `delegation` console command
- release checklist
- changelog
- contribution guide, security policy, issue templates, and PR template
- Apache-2.0 license decision before broad public launch
- TestPyPI release before PyPI
- compatibility wrappers for existing `scripts/*.py` commands

## Growth Loops

### Developer Aha Loop

1. Copy a Harnessfile.
2. Run `delegation plan`.
3. See a readable execution plan.
4. Run in dry-run mode.
5. Inspect the ledger.
6. Star because the idea is immediately useful even before live execution.

### Contributor Loop

1. Find a clear good-first issue.
2. Add one adapter, eval, playbook, or doc example.
3. Run `python scripts/qa.py`.
4. See their contribution listed in docs or release notes.
5. Return because the contribution surface is small and meaningful.

### Trust Loop

1. A run fails.
2. The failure becomes a ledger event.
3. The event becomes an eval.
4. The eval prevents regression.
5. Users trust the system more because it gets stricter through use.

## Aspirational Star Milestones

These are target states, not traction claims. The project is still early; stars
should be treated as a lagging signal that the product is becoming useful,
trustworthy, and easy to explain.

- 100 stars: README promise is clear, local dry-run demo works.
- 1,000 stars: GitHub Action flow works, docs are strong, contributors can add evals.
- 10,000 stars: adapter SDK exists, at least 5 real adapters work.
- 100,000 stars: playbook ecosystem and run ledger schema become recognizable.
- 1,000,000 stars: Delegation Bot is the default control plane vocabulary for
  AI work across repositories and harnesses.

## Rules Of The Game

- Build trust before autonomy.
- Enable autonomy through visible promotion.
- Dry-run before apply.
- Evidence before completion.
- Policies before tools.
- Docs before hype.
- Community before scale.
- Legitimate adoption only. No fake stars, paid star campaigns, or artificial
  popularity tricks.

## Next 30 Days

The active queue lives in `docs/next-actions.md`.

Current focus:

1. Add the first local OpenTelemetry export command.
2. Add fixture artifact download examples to README.
3. Add TestPyPI dry-run release notes.
4. Add no-network model-backed suggest fixtures for OpenAI and Anthropic.
5. Add fixture coverage for applied `github.issue` ledger states.

The million-star path starts with one quiet miracle: a developer can understand
what an AI system is about to do before it does it.
