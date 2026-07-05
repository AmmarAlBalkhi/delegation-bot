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

1. Add hosted dashboard wireframe notes.
2. Add Developer Certificate of Origin or contributor-license policy notes.
3. Add playbook catalog filtering by tag and adapter.
4. Add opt-in live model-backed `delegation suggest` after fixture QA exists.
5. Link dry-run feedback update drafts to live GitHub issue numbers.

## Completed Recently

- Added direct `EvalResult` to feedback issue draft conversion.
- Added the first local OpenTelemetry export command.
- Added fixture artifact download examples to README.
- Added TestPyPI dry-run release notes.
- Added no-network model-backed suggest fixtures for OpenAI and Anthropic.
- Added fixture coverage for applied `github.issue` ledger states.

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
