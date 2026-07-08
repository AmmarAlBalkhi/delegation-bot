# App Dashboard

`app-dashboard` is the functional brain for the future DelegationHQ app.

It combines the pieces a user needs on one screen:

- Missions
- Agent Passports
- Approval Inbox
- Evidence
- Timeline
- Settings
- Mission Result
- active request card from real workspace ledger data
- result summary over approval, execution, evidence, attention, and latest
  timeline events
- workspace flow guide from workspace -> agent -> request -> approval ->
  execution -> evidence -> review
- approval preview with reviewer note, expiration, resource scope, evidence
  gaps, and repeated-action history
- control loop checklist for workspace -> mission -> agent -> gate ->
  approval -> execution -> evidence -> timeline/eval
- command center as supporting data, not the main product surface
- next safe actions

```bash
delegation app-dashboard --workspace . --preview-agent local_cli_agent
delegation app-dashboard --workspace . --preview-agent local_cli_agent --preview-note "scope checked"
delegation app-dashboard --workspace . --preview-agent local_cli_agent --json
delegation app-dashboard --workspace . --json
delegation workspace-flow --workspace .
```

When a workspace already has submitted action requests, `app-dashboard` focuses
the active request automatically. Use `--preview-agent` only when you want to
inspect a specific agent before it has submitted a real request.

The local app server can use that same active request to record a guarded
approve/block receipt or register a local Agent Passport when it is started
with:

```bash
delegation app-serve --workspace . --allow-actions
```

Those write paths only update local control-plane files. They do not execute
the agent, call GitHub, or call models.

Simple version:

```text
Show me the workspace.
Show me the mission.
Show me the agent request.
Show me if it is safe.
Show me what it can touch.
Show me if it happened before.
Show me the evidence.
Show me the result.
Show me the timeline.
Show me the next safe step.
```

## JSON Contract

The JSON output is meant for the local browser shell, future Windows EXE, and
future hosted/team surfaces.

Top-level fields:

- `state`: app-ready workspace state
- `active_request`: the highest-priority real request card from the workspace
  ledger, if one exists
- `request_cards`: all current request cards from the Approval Inbox
- `approval_preview`: human card for the current agent request, including
  request context, resource summary, evidence status, note/expiration, and
  decision history
- `agent_packet`: Bring Your Own Agent handoff packet when a matching Agent Gate
  receipt exists
- `workspace_flow`: guided local flow stages and the next safe command
- `result_summary`: plain status over the active request, evidence count,
  execution events, attention count, and latest proof trail
- `product_areas`: stable app areas for Missions, Agents, Approval Inbox,
  Evidence, and Settings
- `control_loop`: simple progress checklist for the real trust loop
- `timeline`: ordered proof/history over the ledger
- `command_center`: safe commands the UI can show without guessing
- `next_actions`: deduped next useful actions

## Boundary

This command is read-only. It does not execute agents, call GitHub, call models,
or write approval decisions. The separate `app-serve --allow-actions` mode can
record guarded local approval receipts and Agent Passport registrations.

Design can change later. The important product contract is the data shape.
RunPrint is currently one evidence tool; the dashboard should keep saying
Evidence so more recorder, eval, monitoring, and business-workflow tools can
fit later.
