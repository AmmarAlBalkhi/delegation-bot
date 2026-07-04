# Next Actions

This is the active work queue. Keep it short so the project does not drift.

## Core Idea

Delegation Bot is a harness for AI harnesses:

```text
Harnessfile -> dry-run plan -> policy gates -> adapter actions -> run ledger -> evals -> promotion
```

Everything should strengthen that loop.

The trust model is hybrid:

```text
AI proposes.
Delegation Bot verifies.
Human approves risky actions.
Ledger records everything.
Evals decide whether trust increases.
```

The experience rule is:

```text
Useful in 60 seconds.
Powerful after 10 minutes.
Deep only when the user asks for depth.
```

## Now

1. Add model-backed `delegation suggest` design notes behind explicit opt-in.
2. Add repeat-threshold policy for blocked eval feedback.
3. Add the first local OpenTelemetry export command.
4. Add fixture artifact download examples to README.
5. Add TestPyPI dry-run release notes.

## Next

1. Implement the first live `github.issue` execution gate.
2. Add hosted dashboard wireframe notes.
3. Add Developer Certificate of Origin or contributor-license policy notes.
4. Add playbook catalog filtering by tag and adapter.
5. Add compatibility badges once live-gated adapters exist.

## Later

1. Hosted dashboard prototype.
2. GitHub App installation flow.
3. Team approval workflows.
4. Slack, Linear, Jira, and enterprise adapters.
5. Domain landing page and waitlist.
6. Trademark, hosted terms, and privacy-policy planning.

## Parking Lot

These matter, but should not interrupt the core loop:

- pricing
- domain purchase
- logo and visual identity
- hosted billing
- marketplace strategy
- long-form launch content

See `docs/business-model.md` and `docs/domain-strategy.md` for those threads.
