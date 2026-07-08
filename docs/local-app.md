# Local App Shell

DelegationHQ now has a functional local app shell over the control plane.

This is not the final visual design. The interface direction still waits for
maintainer approval. The goal of this slice is to prove the app can turn on,
read a workspace, show agents, show approval previews, and stay local-first.

## Commands

```bash
delegation workspace-init --path . --plan
delegation agent-add local_cli_agent --workspace . --command "python agent.py" --capability read.workspace --allowed-data workspace --evidence command_output --force
delegation approval-preview local_cli_agent --workspace .
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

- workspace health
- ledger status
- registered Agent Passports
- release readiness
- a human approval preview card
- next safe actions

Simple version:

```text
Folder is workspace.
Agents have ID cards.
App shows current state.
Approval card says allow, ask human, or block.
Live actions still need guarded commands.
```

## Boundaries

- `app-export` writes static files only.
- `app-serve` serves local state only.
- Neither command executes agents.
- Neither command writes to GitHub.
- Final visual/interface design should be approved before styling this into the
  futuristic product UI.
