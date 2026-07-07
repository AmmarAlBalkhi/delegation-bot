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
- `app-state` can include gate-ready data
- docs show simple examples without asking users to write many rules
- full QA passes

## Later

After the first gate works, connect it to RunPrint:

```text
planned intent -> approved gate -> recorded reality -> eval judgment
```

That comparison is where DelegationHQ becomes stronger than a planner or a
recorder alone.
