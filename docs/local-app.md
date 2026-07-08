# Local App Shell

DelegationHQ now has a functional local app shell over the control plane.

This is not the final visual design. The interface direction still waits for
maintainer approval. The goal of this slice is to prove the app can turn on,
read a real workspace, show agents, show approval previews, show evidence, and
stay local-first.

## Commands

```bash
delegation workspace-init --path . --plan
delegation workspace-demo --path .delegation/demo-workspace --approve --execute --confirm LOCAL_AGENT_EXECUTION --export-app
delegation agent-add local_cli_agent --workspace . --command "python agent.py" --capability read.workspace --allowed-data workspace --evidence command_output --force
delegation action-request local_cli_agent --workspace . --action read.workspace --target workspace --summary "Agent requests workspace access."
delegation approval-preview local_cli_agent --workspace . --review-note "scope checked" --expires-at 2099-01-01T00:00:00Z
delegation workspace-flow --workspace .
delegation app-dashboard --workspace .
delegation timeline --workspace .
delegation app-export --workspace .
delegation app-serve --workspace . --dry-run
delegation app-serve --workspace . --allow-actions
```

Open the exported file:

```text
.delegation/cockpit/index.html
```

Or run the server:

```bash
delegation app-serve --workspace .
```

Then open:

```text
http://127.0.0.1:8765/
```

By default the server is read-only. If you want the local app backend to record
an approve/block decision for the active request, start it deliberately:

```bash
delegation app-serve --workspace . --allow-actions
```

The browser-facing approval endpoint still requires the exact confirmation token
`LOCAL_APP_WRITE`. This only records the human approval receipt. Agent execution
still requires the separate `LOCAL_AGENT_EXECUTION` confirmation through the
controlled request-run path.

## What It Shows

- Missions
- Agents
- Approval Inbox
- Evidence
- Timeline
- Settings
- workspace health
- active request from the real workspace ledger
- guided workspace flow with the current step and one next safe command
- one-command demo workspace with optional approval, execution, evidence, and
  cockpit export
- registered Agent Passports
- a human approval preview card with request context, action intent, command
  preview, resource scope, evidence gaps, history, reviewer notes, and
  expiration
- a full mission timeline
- copy buttons for commands
- richer Agent Passport details with endpoint, scope, trust, warnings, and
  preview commands
- local data links for generated JSON files in Settings
- next safe actions
- guarded local approval writes when the server is started with `--allow-actions`

Simple version:

```text
Folder is workspace.
Mission is the objective.
Agents have ID cards.
Approval card says allow, ask human, or block.
Action intent says what may happen before you say yes.
Workspace flow says what to do next.
Active request says what the agent is asking for now.
Evidence says what was recorded.
Timeline shows everything that happened.
Settings keeps maintenance details out of the main loop.
```

## Boundaries

- `app-export` writes static files only.
- `app-serve` is read-only unless started with `--allow-actions`.
- `--allow-actions` can record a local approve/block receipt only when the
  request includes `LOCAL_APP_WRITE`.
- Agent execution still requires `LOCAL_AGENT_EXECUTION`.
- Neither app command executes agents.
- Neither command writes to GitHub.
- RunPrint is the current recorder path, not the whole product. Future evidence
  tools should fit behind the same Evidence area.
- Visual design can change later because the app reads `dashboard.json`,
  `state.json`, `timeline.json`, and approval preview JSON.
- Final visual/interface design should be approved before styling this into the
  futuristic product UI.
