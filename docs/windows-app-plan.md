# Windows EXE App Plan

DelegationHQ already has a Windows `delegation.exe` packaging path. The next
step is not a generic desktop app. It is a local mission cockpit for agentic
work.

Simple version:

```text
Open the app.
See the mission.
See what is safe.
See what proof exists.
Approve risky actions only when ready.
```

## First Target

The first visible app should be local-first and read-only by default.

It should consume the same command-backed data that already works:

- `delegation demo`
- `delegation doctor`
- `delegation app-state --json`
- `delegation agents --json`
- `delegation dashboard --json`
- `delegation evidence --json`
- `delegation release-check`

That keeps the app honest. The CLI stays the engine; the app becomes the cockpit.

## App Surfaces

1. First Run

   Run demo, doctor, and starter Harnessfile creation without asking users to
   understand Python packaging.

2. Mission Snapshot

   Show Harnessfile objective, status, next safe action, evals, adapters, and
   agents from the dashboard snapshot.

3. Evidence

   Show planned proof bundles from `delegation evidence`, including ledger,
   eval, approval, and workflow proof requirements.

4. Agent Passports

   Support Bring Your Own Agent by showing registered custom agents, runtime
   type, capabilities, allowed tools/data, risk level, expected outputs, and
   promotion evals. The first command-backed source is `delegation agents`.

5. Approval Inbox

   Preview risky actions before live GitHub writes, workflow dispatch, agent
   execution, API/webhook calls, or custom-agent actions.

## Bring Your Own Agent

DelegationHQ should not be one agent. It should be the control layer above any
agent.

The app should eventually let users register:

- LangGraph agents
- CRM/RAG agents
- coding agents
- CLI agents
- MCP workflows
- API/webhook agents
- local tools

Each registered agent needs an Agent Passport:

- agent id and display name
- runtime type
- command, API endpoint, webhook, MCP endpoint, or local tool entrypoint
- capabilities
- allowed tools and data
- risk level
- required approvals
- expected outputs
- evidence requirements
- evals required for promotion

## Guardrails

- The first app slice is read-only by default.
- No model calls happen unless the user explicitly opts in.
- No live writes happen without exact confirmation gates.
- No agent execution happens just because an agent is registered.
- The app uses existing JSON reports before inventing new state.
- Visual/interface design waits for maintainer approval.

## First Command

Inspect the current app plan:

```bash
delegation app-plan
delegation app-plan --json
```

Inspect the app-ready state bundle:

```bash
delegation demo --ledger .delegation/demo.jsonl
delegation app-state --ledger .delegation/demo.jsonl
delegation app-state --ledger .delegation/demo.jsonl --json
delegation agents examples/ai-harness-control-plane.yaml --registry examples/agent-passports.yaml
delegation agents examples/ai-harness-control-plane.yaml --registry examples/agent-passports.yaml --json
delegation agent-gate examples/ai-harness-control-plane.yaml implementer --action create_pull_request --target repository
delegation approval-inbox --ledger .delegation/demo.jsonl --json
delegation runprint-ingest --ledger .delegation/demo.jsonl --action-id agent_gate.implementer.create_pull_request --recording-id rec-demo --bundle-id bundle-demo --artifact run-ledger:jsonl:.delegation/demo.jsonl --json
```

`app-state` is the first backend slice for the local cockpit. It combines the
app plan, doctor report, release readiness, mission dashboard, evidence bundle
summary, approval inbox summary, recorded-evidence receipts, next safe action,
and guardrails without launching a UI or doing live work.

## Milestones

1. `app-plan` exists and is covered by tests.
2. `app-state` exists as one read-only JSON feed for the future local cockpit.
3. The Windows EXE can run `demo`, `doctor`, `dashboard`, `evidence`,
   `app-plan`, and `app-state`.
4. `agents` shows Harnessfile and custom registry Agent Passports.
5. `agent-gate` previews whether an agent action should allow, warn, require
   approval, or block.
6. A local app shell reads app-state JSON, Agent Passport JSON, and Agent Gate
   preview JSON.
7. Approval Inbox previews risky actions without live execution.
8. RunPrint ingest attaches recorded evidence to approval cards.
9. The app is packaged from a tagged commit with checksums and release rehearsal
   evidence.

## Design Boundary

The actual interface should not be built until the visual direction is approved.

The product direction can be futuristic and cool without becoming confusing.
The app should feel like mission control: powerful, calm, fast, and obvious
about what is safe versus risky.
