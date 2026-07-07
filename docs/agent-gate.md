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

## First Command Shape

```bash
delegation agent-gate examples/ai-harness-control-plane.yaml planner \
  --action create_pull_request \
  --target repository
```

Custom agents should work too:

```bash
delegation agent-gate --registry examples/agent-passports.yaml crm_update_agent \
  --action crm.write \
  --target crm.accounts
```

## Inputs

The first version should accept:

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
Agent: planner
Action: create_pull_request
Target: repository
Risk: medium
Reason: pull_request requires human approval.
Required approvals: pull_request
Required evidence: run_ledger, adapter_result, eval_report
Next: collect approval before live action
```

JSON output should carry the same fields for `app-state` and future UI work.

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
- if action/target is outside the passport, block
- if action matches required approvals, require approval
- if risk is high or critical and no approval exists, require approval or block
- if evidence requirements are missing, warn or require approval
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
