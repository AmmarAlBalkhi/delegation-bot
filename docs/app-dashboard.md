# App Dashboard

`app-dashboard` is the functional brain for the future DelegationHQ app.

It combines the pieces a user needs on one screen:

- workspace health
- Agent Passports
- approval preview
- command center
- mission timeline
- next safe actions

```bash
delegation app-dashboard --workspace . --preview-agent local_cli_agent
delegation app-dashboard --workspace . --preview-agent local_cli_agent --json
```

Simple version:

```text
Show me the workspace.
Show me the agent request.
Show me if it is safe.
Show me the next command.
Show me the proof trail.
```

## JSON Contract

The JSON output is meant for the local browser shell, future Windows EXE, and
future hosted/team surfaces.

Top-level fields:

- `state`: app-ready workspace state
- `approval_preview`: human card for the current agent request
- `timeline`: ordered proof/history over the ledger
- `command_center`: safe commands the UI can show without guessing
- `next_actions`: deduped next useful actions

## Boundary

This command is read-only. It does not execute agents, call GitHub, call models,
or write approval decisions.

Design can change later. The important product contract is the data shape.
