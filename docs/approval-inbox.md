# Approval Inbox

The approval inbox turns Agent Gate receipts into simple human-review cards.

Simple version:

```text
Agent asks to do work.
Agent Gate writes a receipt.
Approval Inbox shows the card.
Human approves or blocks.
Ledger keeps the decision.
```

## Commands

Show cards from a ledger:

```bash
delegation approval-inbox --ledger .delegation/demo.jsonl
```

Record a human decision:

```bash
delegation approval-decision \
  --ledger .delegation/demo.jsonl \
  --action-id agent_gate.implementer.create_pull_request \
  --decision approve \
  --approver Ammar
```

Attach recorded evidence after the recorder runs:

```bash
delegation runprint-ingest \
  --ledger .delegation/demo.jsonl \
  --action-id agent_gate.implementer.create_pull_request \
  --recording-id rec-demo \
  --bundle-id bundle-demo \
  --artifact run-ledger:jsonl:.delegation/demo.jsonl
```

Block instead:

```bash
delegation approval-decision \
  --ledger .delegation/demo.jsonl \
  --action-id agent_gate.implementer.create_pull_request \
  --decision block \
  --approver Ammar \
  --reason "Too broad for this mission."
```

These commands do not execute the agent, write to GitHub, call a model, or
grant new powers. They only write local ledger evidence.

## Card States

- `pending_approval`: a human must approve or block
- `approved`: approval evidence exists
- `blocked_by_human`: a human blocked the intent
- `blocked_by_gate`: Agent Gate blocked the intent
- `needs_evidence`: gate passed, but recorder evidence is missing
- `ready_for_recording`: gate and evidence plan are ready
- `recorded`: an evidence tool recorded execution proof for this card
- `warning`: review before increasing autonomy

## Why It Matters

This keeps the user experience simple:

```text
This agent wants to do X.
Risk: medium.
Evidence: planned.
Decision needed: approve or block.
```

The deeper machinery stays in the ledger for evals, promotion, and future app
views.
