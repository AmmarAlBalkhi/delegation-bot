# Roadmap: AI Delegation Control Plane

This roadmap keeps DelegationHQ focused on the core product: a trustworthy,
portable control plane for agentic work.

## One-Sentence Product

DelegationHQ is the mission control layer for AI work: write one Harnessfile,
dry-run the plan, route work to any agent harness, enforce policy, and get an
auditable run ledger with evals.

It should enable agents, not suppress them. The project gives agents an autonomy
ladder: suggest, draft, act, operate, deploy.

The trust model is hybrid:

```text
AI proposes.
DelegationHQ verifies.
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
delegation plan examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl
```

### 1. GitHub-Native Control Plane

Goal: A repository can run DelegationHQ as a GitHub Action and use Issues as the
visible coordination surface.

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
- Agent Passport registry for Bring Your Own Agent
- local workspace init/status so GitHub is optional instead of required
- workspace-aware app state and local cockpit backend
- one-screen app dashboard bundle with command center and approval preview
- mission timeline over plan/gate/approval/execution/proof/eval events
- custom agent registration without hand-editing large YAML files
- controlled command-backed agent execution with local evidence capture
- human approval preview cards for agent requests
- static local app export and local app server dry-run
- local app JSON feeds for dashboard, state, timeline, and approval preview
- agent gate previews for requested actions
- mission status over the plan/gate/approval/proof loop
- agent packets for custom agent handoff
- autonomy ladder
- capability packs
- promotion rules based on evals and ledger evidence
- promotion reports that show ready vs blocked agents
- approval previews that return allow, warn, approval required, or block
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

### 4. Playbook Ecosystem

Goal: Teams can share reusable Harnessfiles for common AI work.

Deliverables:

- `playbooks/` convention
- starter playbooks for code review, weekly planning, release readiness,
  documentation refresh, and CI repair
- contribution guidelines for playbooks
- compatibility metadata for adapters and policies

### 5. AgentOps Standard Library

Goal: DelegationHQ becomes a clear open-source vocabulary for trustworthy AI
delegation.

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

1. Run `delegation demo`.
2. Create or copy a Harnessfile.
3. See a readable dry-run plan.
4. Inspect the ledger.
5. Add one playbook, eval, or adapter when ready.

### Contributor Loop

1. Find a clear good-first issue.
2. Add one adapter, eval, playbook, or doc example.
3. Run `python scripts/qa.py`.
4. See the contribution listed in docs or release notes.
5. Return because the contribution surface is small and meaningful.

### Trust Loop

1. A run fails.
2. The failure becomes a ledger event.
3. The event becomes an eval.
4. The eval prevents regression.
5. Users trust the system more because it gets stricter through use.

## Adoption Milestones

Treat adoption as a lagging signal that the product is becoming useful,
trustworthy, and easy to explain. The public goal is not hype; it is repeat use.

- clear README promise and local dry-run demo
- GitHub Action flow and strong contributor docs
- adapter SDK with real adapter examples
- recognizable playbook ecosystem and run ledger schema
- stable vocabulary for AI delegation across repositories and harnesses

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

1. Make Bring Your Own Agent practical: agent packets, starter registries, and
   examples for CLI, API/webhook, MCP, CRM, LangGraph, Codex, and Claude-style
   workers.
2. Keep the visible loop simple: plan, gate, approve, record, status, packet.
3. Improve the local app shell after visual direction is approved.
4. Add richer Agent Approval Preview cards over proposed file/resource diffs,
   command intent, reviewer notes, expiration, and repeated-action history.
5. Align RunPrint ingest with the standalone RunPrint bundle schema as it
   stabilizes.
6. Run the Windows `.exe` build script on a clean Windows release host and
   record the executable smoke evidence.

The adoption path starts with one quiet miracle: a developer can understand what
an AI system is about to do before it does it.
