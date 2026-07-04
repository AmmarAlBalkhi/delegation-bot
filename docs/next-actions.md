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

1. Add the first local OpenTelemetry export command.
2. Add fixture artifact download examples to README.
3. Add TestPyPI dry-run release notes.
4. Add no-network model-backed suggest fixtures for OpenAI and Anthropic.
5. Add fixture coverage for applied `github.issue` ledger states.

## Next

1. Add direct `EvalResult` to feedback issue draft conversion.
2. Add hosted dashboard wireframe notes.
3. Add Developer Certificate of Origin or contributor-license policy notes.
4. Add playbook catalog filtering by tag and adapter.
5. Add opt-in live model-backed `delegation suggest` after fixture QA exists.

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
