# Local-First Workspaces

DelegationHQ must work when GitHub is not involved.

GitHub is an adapter. The core product is the control loop:

```text
plan -> gate -> approve -> record -> ledger -> eval -> promote
```

## Start Any Folder

From a folder you want to control:

```bash
delegation workspace-init --path . --plan
delegation workspace-status --path .
```

This creates:

- `.delegation/Harnessfile.yaml`
- `.delegation/agents.yaml`
- `.delegation/local-workspace.jsonl` when `--plan` is used

Simple version:

```text
Folder becomes workspace.
Agent gets ID card.
Gate checks danger.
Ledger keeps proof.
```

## Add Your Own Agent

Register a local CLI agent:

```bash
delegation agent-add research_agent --command "python agents/research_agent.py" --capability read.workspace --allowed-data workspace --evidence command_output
```

Preview what it may do:

```bash
delegation agent-gate --registry .delegation/agents.yaml research_agent --action read.workspace --target workspace
```

Run it under control:

```bash
delegation agent-run research_agent --registry .delegation/agents.yaml --ledger .delegation/agent-run.jsonl --action read.workspace --target workspace --execute --confirm LOCAL_AGENT_EXECUTION
delegation agent-audit --ledger .delegation/agent-run.jsonl
```

The custom agent does the work. DelegationHQ controls:

- identity
- runtime type
- allowed tools and data
- risky actions
- approvals
- required evidence
- evals for promotion

`agent-run` only executes command-backed agents after the exact confirmation
token. It records the gate receipt, command output, exit code, duration, and a
RunPrint-style evidence receipt in the ledger.

## Why This Matters

Users should not need to configure forty YAML rules before seeing value.

The first experience should be:

```text
add agent -> give mission -> preview risk -> approve/block -> record evidence -> review result
```

Local-first support makes DelegationHQ useful for:

- codebases
- research folders
- Obsidian vaults
- CRM export folders
- local tools
- private agent experiments

GitHub, MCP, LangGraph, Claude Code, OpenAI Agents SDK, webhooks, and hosted
systems can plug in later through adapters.
