---
name: Adapter request
about: Request support for a new harness, workflow, tool, or agent runtime
title: "Adapter: "
labels: ["adapter", "trust-layer"]
---

## Adapter target

What system should DelegationHQ plan or run?

Examples: `crew.ai`, `autogen.agent`, `linear.issue`, `jira.issue`,
`slack.message`, `shell.command`, a private internal harness, or a new model
runtime.

## Use case

What should a user be able to delegate?

## Dry-run first

What should the adapter prove without making a live write, model call, or agent
execution?

## Inputs

What does the adapter need?

## Outputs

What evidence or artifacts should it produce?

## Ledger events

What events should be written so users can inspect what happened later?

## Risk and approvals

What could go wrong, and what should require human approval?

## Acceptance criteria

- [ ] Adapter contract is documented.
- [ ] Dry-run output includes required evidence.
- [ ] Tests cover good, blocked, and failed paths when relevant.
- [ ] Docs explain the user workflow in simple language.
