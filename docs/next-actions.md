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

1. Link dry-run feedback update drafts to live GitHub issue numbers.
2. Add a real-world adapter candidate matrix.
3. Prototype the read-only dashboard data model with fixture ledgers.
4. Open the first small public roadmap issue set from
   `docs/public-roadmap-issues.md` when maintainers are ready.
5. Add local-model provider design for `delegation suggest`.

## Completed Recently

- Added opt-in live model-backed `delegation suggest` for OpenAI and Anthropic.
- Added explicit `--allow-live-model` gating, API-key checks, model draft
  validation, and mocked provider tests.
- Made default `delegation suggest` output shorter and less boring.
- Added public roadmap issue drafts.
- Added issue label source of truth and good-first-issue curation notes.
- Added GitHub App installation design notes.
- Improved issue templates for adapters, evals, playbooks, bugs, and design
  proposals.
- Added hosted dashboard wireframe notes.
- Added Developer Certificate of Origin and contributor-license policy notes.
- Added playbook catalog filtering by tag and adapter.
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
