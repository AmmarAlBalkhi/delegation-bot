# Agent Gate

Agent Gate is the next control-plane primitive after Agent Passports.

Simple version:

```text
Agent says: I want to do this.
DelegationHQ checks the passport.
DelegationHQ returns: allow, warn, approval required, or block.
```

## Why This Exists

A passport alone is an ID card. The gate is the guard at the door.

DelegationHQ should enable agents, not oppress them. The gate makes autonomy
earned and understandable:

- safe actions can continue
- unclear actions can warn
- risky actions need human approval
- forbidden actions are blocked
- every decision names the evidence that must be recorded

## Command Shape

```bash
delegation agent-gate examples/ai-harness-control-plane.yaml implementer \
  --action create_pull_request \
  --target repository
```

Custom agents should work too:

```bash
delegation agent-gate --registry examples/agent-passports.yaml crm_update_agent \
  --action crm.write \
  --target crm.accounts
```

If approval evidence already exists, pass it explicitly:

```bash
delegation agent-gate examples/ai-harness-control-plane.yaml implementer \
  --action create_pull_request \
  --target repository \
  --approval pull_request
```

To make the preview part of the mission timeline, write a gate receipt into
the same ledger:

```bash
delegation agent-gate examples/ai-harness-control-plane.yaml implementer \
  --action create_pull_request \
  --target repository \
  --approval pull_request \
  --ledger .delegation/demo.jsonl \
  --write
```

Then compare that intent receipt with recorder evidence:

```bash
delegation agent-audit --ledger .delegation/demo.jsonl
```

Or show a human-review card first:

```bash
delegation approval-inbox --ledger .delegation/demo.jsonl
delegation approval-decision --ledger .delegation/demo.jsonl \
  --action-id agent_gate.implementer.create_pull_request \
  --decision approve \
  --approver Ammar
delegation evidence-ingest --ledger .delegation/demo.jsonl \
  --tool test-reporter \
  --tool-kind test \
  --action-id agent_gate.implementer.create_pull_request \
  --recording-id rec-demo \
  --bundle-id bundle-demo \
  --artifact test-report:junit:artifacts/tests.xml
delegation mission-status --ledger .delegation/demo.jsonl
delegation agent-packet --ledger .delegation/demo.jsonl \
  --action-id agent_gate.implementer.create_pull_request
delegation agent-result-ingest --ledger .delegation/demo.jsonl \
  --action-id agent_gate.implementer.create_pull_request \
  --result .delegation/agent-result.json
```

Simple version:

```text
Agent Gate = receipt for what the agent wanted to do.
Approval Inbox = card for the human.
RunPrint = current proof recorder, not the whole evidence layer.
Agent audit = compare receipt with proof.
Mission Status = plain answer for what is done and what is next.
Agent Packet = safe job card for an outside custom agent.
Agent Result = worker comes back with proof in a shape DelegationHQ can judge.
```

The command also supports JSON for future app/cockpit use:

```bash
delegation agent-gate --registry examples/agent-passports.yaml repo_cli_agent \
  --action read.run_ledger \
  --target run_ledger \
  --json
```

## Inputs

The command accepts:

- agent id
- requested action
- target resource, file, tool, or data scope
- optional requested risk
- optional evidence already present
- optional Agent Passport registry
- optional ledger path when `--write` is used

## Output

The report should stay simple:

```text
Agent Gate

Decision: approval_required
Status: approval_required
Agent: implementer
Action: create_pull_request
Target: repository
Risk: medium
Checks:
- [PASS] scope.action: Action matches capability `write.pull_request_draft`.
- [PASS] scope.target: Target is inside allowed scope.
- [APPROVAL] approval.required: Human approval is required for pull_request.
Required approvals:
- pull_request
Required evidence:
- run_ledger
- adapter_result
Next:
- Collect approval evidence before live action.
```

JSON output should carry the same fields for `app-state` and future UI work.

## Agent Packet

`delegation agent-packet` turns a gate receipt into a Bring Your Own Agent
handoff packet.

Simple version:

```text
The gate decides.
The packet explains the decision to the worker agent.
The worker agent stays inside that packet.
An evidence recorder captures what happened.
```

The packet includes agent identity, runtime type, requested action, target,
allowed tools/data, missing approvals, required evidence, and a small return
contract. This lets DelegationHQ supervise Codex, Claude Code, LangGraph, CRM
agents, MCP workflows, webhook agents, local CLI tools, and future harnesses
without becoming those agents.

## Agent Result Ingest

`delegation agent-result-ingest` is the return lane for custom agents. It reads
the worker result JSON, checks the agent/action/packet identity, requires
RunPrint recording ids, then appends:

- `agent.result.reported`
- `runprint.recording.completed`

Simple version:

```text
Packet = job card.
Agent result = worker's answer.
Result ingest = bouncer checks the answer before it enters the ledger.
```

## Ledger Receipt

`--write --ledger LEDGER` appends one JSONL event:

```text
type: agent.gate.previewed
status: allow | warn | approval_required | block
details.agent_gate: full Agent Gate report
```

This does not execute the agent. It records the decision so approval evidence,
Recorder evidence, evals, and promotion checks can share one timeline.

## Evidence Audit

`delegation agent-audit --ledger LEDGER` reads the ledger and returns:

- `missing_gate` when no Agent Gate receipt exists
- `approval_required` when the receipt still needs human approval
- `needs_evidence` when the gate allowed work but no recorder evidence plan was found
- `ready_for_recording` when the gate allowed work and a recorder evidence bundle is planned
- `recorded` when live evidence recording events are present
- `blocked` when the gate blocked the intent

Today planned evidence often comes from `runprint.recorder`. That is honest: it
says the camera has a plan. Recorded evidence can come through the generic
`evidence-ingest` lane or the RunPrint-specific compatibility lane.

## Approval Is Not Permission

Human approval unlocks work the passport already allows. It does not create a
new power.

Example:

```text
implementer can draft pull requests -> approval_required
planner tries to create a pull request -> block
```

This keeps the system enabling but honest. The right agent can move forward
with approval. The wrong agent is stopped before it reaches live action.

## Decisions

- `allow`: action matches declared capabilities, data/tool scope, and no
  approval is needed
- `warn`: action is close to allowed scope but missing non-critical context
- `approval_required`: action is allowed only after a human approval
- `block`: action is outside the passport, blocked by policy, or missing
  required identity/scope

## First Rules

The first implementation should be deterministic:

- if the agent is unknown, block
- if action or target is outside the passport, block
- if action matches required approvals, require approval
- if risk is high or critical and no approval policy exists, block
- if risk is high or critical and approval is missing, require approval
- if evidence requirements are missing from the passport, warn
- if everything is inside scope and low risk, allow

## Done Means

- `delegation agent-gate` has human and JSON output
- Harnessfile agents and custom registry agents both work
- focused tests cover allow, warn, approval required, block
- `--write --ledger` records Agent Gate preview receipts
- `delegation agent-audit` compares gate intent with recorder evidence
- `app-state` can include gate-ready data
- docs show simple examples without asking users to write many rules
- full QA passes

## Later

After planned evidence works, connect it to live RunPrint recording:

```text
planned intent -> approved gate receipt -> recorded reality -> eval judgment
```

That comparison is where DelegationHQ becomes stronger than a planner or a
recorder alone.
