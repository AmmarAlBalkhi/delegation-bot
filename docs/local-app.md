# Local App Shell

DelegationHQ now has a functional local app shell over the control plane.

This is not the final visual design. The interface direction still waits for
maintainer approval. The goal of this slice is to prove the app can turn on,
read a real workspace, show agents, show approval previews, show evidence, and
stay local-first.

## Commands

```bash
delegation workspace-init --path . --plan
delegation agent-add local_cli_agent --workspace . --command "python agent.py" --capability read.workspace --allowed-data workspace --evidence command_output --force
delegation approval-preview local_cli_agent --workspace . --review-note "scope checked" --expires-at 2099-01-01T00:00:00Z
delegation app-dashboard --workspace . --preview-agent local_cli_agent --preview-note "scope checked"
delegation timeline --workspace .
delegation app-export --workspace . --preview-agent local_cli_agent
delegation app-serve --workspace . --dry-run
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

## What It Shows

- Missions
- Agents
- Approval Inbox
- Evidence
- Timeline
- Settings
- workspace health
- registered Agent Passports
- a human approval preview card with request context, resource scope, evidence
  gaps, history, reviewer notes, and expiration
- a full mission timeline
- copy buttons for commands
- richer Agent Passport details with endpoint, scope, trust, warnings, and
  preview commands
- local data links for generated JSON files in Settings
- next safe actions

Simple version:

```text
Folder is workspace.
Mission is the objective.
Agents have ID cards.
Approval card says allow, ask human, or block.
Evidence says what was recorded.
Timeline shows everything that happened.
Settings keeps maintenance details out of the main loop.
```

## Boundaries

- `app-export` writes static files only.
- `app-serve` serves local state only.
- Neither command executes agents.
- Neither command writes to GitHub.
- RunPrint is the current recorder path, not the whole product. Future evidence
  tools should fit behind the same Evidence area.
- Visual design can change later because the app reads `dashboard.json`,
  `state.json`, `timeline.json`, and approval preview JSON.
- Final visual/interface design should be approved before styling this into the
  futuristic product UI.
