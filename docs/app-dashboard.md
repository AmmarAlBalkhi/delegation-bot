# App Dashboard

`app-dashboard` is the functional brain for the future DelegationHQ app.

It combines the pieces a user needs on one screen:

- Missions
- Agent Passports
- Approval Inbox
- Evidence
- Timeline
- Settings
- approval preview with reviewer note, expiration, resource scope, evidence
  gaps, and repeated-action history
- command center as supporting data, not the main product surface
- next safe actions

```bash
delegation app-dashboard --workspace . --preview-agent local_cli_agent
delegation app-dashboard --workspace . --preview-agent local_cli_agent --preview-note "scope checked"
delegation app-dashboard --workspace . --preview-agent local_cli_agent --json
```

Simple version:

```text
Show me the workspace.
Show me the mission.
Show me the agent request.
Show me if it is safe.
Show me what it can touch.
Show me if it happened before.
Show me the evidence.
Show me the timeline.
```

## JSON Contract

The JSON output is meant for the local browser shell, future Windows EXE, and
future hosted/team surfaces.

Top-level fields:

- `state`: app-ready workspace state
- `approval_preview`: human card for the current agent request, including
  request context, resource summary, evidence status, note/expiration, and
  decision history
- `agent_packet`: Bring Your Own Agent handoff packet when a matching Agent Gate
  receipt exists
- `product_areas`: stable app areas for Missions, Agents, Approval Inbox,
  Evidence, and Settings
- `timeline`: ordered proof/history over the ledger
- `command_center`: safe commands the UI can show without guessing
- `next_actions`: deduped next useful actions

## Boundary

This command is read-only. It does not execute agents, call GitHub, call models,
or write approval decisions.

Design can change later. The important product contract is the data shape.
RunPrint is currently one evidence tool; the dashboard should keep saying
Evidence so more recorder, eval, monitoring, and business-workflow tools can
fit later.
