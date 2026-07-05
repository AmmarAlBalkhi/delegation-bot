# Hosted Dashboard Wireframe Notes

The dashboard should come after the CLI loop is loved. It should not replace
the Harnessfile, ledger, evals, or approval gates. It should make them easier
to see.

Simple version:

```text
CLI is engine.
Dashboard is cockpit.
Ledger is black box.
```

## Product Goal

The hosted dashboard should answer five questions fast:

1. What is the AI mission trying to do?
2. What will happen before anything goes live?
3. What is blocked and why?
4. What evidence exists?
5. Which agents have earned more autonomy?

## First Screen

```text
Delegation Bot

[Mission] [Plan] [Ledger] [Evals] [Agents] [Playbooks]

Mission: release readiness
Status: blocked on test evidence
Mode: dry-run
Harnessfile: playbooks/release-readiness.yaml
Run ledger: .delegation/latest.jsonl

Next safe action:
Run tests, append test evidence, then rerun promotion.
```

The first screen should feel like mission control, not analytics homework.

## Core Views

### Mission

- objective
- current mode: dry-run, preview, apply
- source Harnessfile
- repository
- owners and reviewers
- latest run status
- next safe action

### Plan

- ordered action list
- adapter per action
- risk level
- approval requirement
- dry-run vs live
- blocked gates

### Ledger

- recent events
- adapter evidence
- artifacts
- sanitized details
- links to downloaded workflow artifacts

### Evals

- passed, blocked, failed counts
- failed eval details
- feedback issue draft preview
- regression or playbook follow-up

### Agents

- agent passport
- runtime
- model
- autonomy level
- required evals for promotion
- ready vs blocked promotion state

### Playbooks

- catalog search
- tag filters
- adapter filters
- expected eval states
- copy command

## Design Rules

- Summary first, details on demand.
- Every blocked state needs a next action.
- Never hide live writes behind a friendly button.
- Make dry-run the obvious default.
- Show proof before trust.
- Keep raw JSON available, but not required for understanding.

## First Hosted Prototype Boundary

The first prototype should be read-only:

- upload or point to a ledger file
- parse a Harnessfile
- show catalog playbooks
- show eval and promotion state
- no live GitHub writes
- no model calls
- no agent execution

Live operations should remain in the CLI until the policy and approval model is
boring and proven.
