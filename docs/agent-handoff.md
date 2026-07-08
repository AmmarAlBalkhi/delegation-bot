# Agent Handoff

DelegationHQ should control any agent without becoming that agent.

Simple version:

```text
DelegationHQ gives the worker a job card.
The worker does the work.
RunPrint records what happened.
The worker returns a result.
DelegationHQ checks the result before trust increases.
```

## Flow

```bash
delegation agent-gate examples/ai-harness-control-plane.yaml implementer \
  --action create_pull_request \
  --target repository \
  --approval pull_request \
  --ledger .delegation/demo.jsonl \
  --write

delegation agent-packet \
  --ledger .delegation/demo.jsonl \
  --action-id agent_gate.implementer.create_pull_request \
  --output .delegation/agent-packet.json

delegation agent-result-ingest \
  --ledger .delegation/demo.jsonl \
  --action-id agent_gate.implementer.create_pull_request \
  --result .delegation/agent-result.json
```

The external agent can be a CLI tool, webhook worker, LangGraph app, MCP
workflow, coding agent, CRM agent, local script, or future hosted worker. The
contract is the same.

## Result JSON

```json
{
  "schema_version": "delegation.agent-result.v1",
  "packet_id": "agent_packet_...",
  "action_id": "agent_gate.implementer.create_pull_request",
  "agent_id": "implementer",
  "status": "completed",
  "summary": "Opened a pull request draft under DelegationHQ control.",
  "changed_resources": ["repository"],
  "runprint_recording_id": "rec-123",
  "evidence_bundle_id": "bundle-123",
  "artifacts": [
    {
      "id": "run-ledger",
      "kind": "jsonl",
      "path": ".delegation/demo.jsonl"
    }
  ]
}
```

Allowed result statuses:

- `completed`
- `partial`
- `failed`
- `blocked`
- `needs_attention`

## Why This Matters

An Agent Passport alone is only an ID card. The handoff loop makes it real:

- packet says what the agent is allowed to do
- result says what the agent claims it did
- RunPrint evidence says what actually happened
- evals decide whether the agent earned more trust

This keeps the user experience simple:

```text
Add agent -> give mission -> preview risk -> approve -> record proof -> review result.
```
