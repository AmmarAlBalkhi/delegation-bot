# Issue Labels

Delegation Bot should keep GitHub Issues useful instead of noisy. Labels should
help people answer one question fast:

```text
What kind of contribution is this, and how does it strengthen the control
plane?
```

The source of truth lives in `.github/labels.yml`.

## Core Labels

- `adapter`: adapter contracts, SDK implementations, and harness integrations
- `eval`: quality, safety, policy, evidence, or regression checks
- `playbook`: reusable Harnessfile workflows and catalog metadata
- `trust-layer`: plans, policies, approvals, ledgers, evidence, evals, or promotion
- `live-gate`: live execution, confirmations, external writes, and approvals
- `github-app`: GitHub App installation, permissions, webhooks, and hosted integration
- `design`: product, architecture, schema, or trust-model design
- `docs`: documentation, examples, README, roadmap, and contributor guidance
- `good first issue`: small scoped work with clear acceptance criteria
- `help wanted`: useful external contribution path

## Label Rules

Use one type label:

- `adapter`
- `eval`
- `playbook`
- `design`
- `docs`
- `bug`

Then add one context label when it helps:

- `trust-layer`
- `live-gate`
- `github-app`
- `roadmap`

Use `good first issue` only when the task has:

- a narrow scope
- clear files to edit
- a local QA command
- no secrets
- no required live GitHub writes
- no model API cost

Simple version:

```text
Good first issue means: small job, clear win, no scary setup.
```

## Good First Issue Candidates

Good first issues should usually be one of these:

- add one compact ledger fixture
- add one playbook catalog example
- improve one doc page
- add one eval test case
- add one no-network adapter fixture
- improve one CLI error message

Avoid marking these as good first issues:

- live execution adapters
- auth flows
- schema migrations
- hosted dashboard security
- model-backed behavior without fixtures
- anything that can write to user repositories

## Applying Labels

Today labels are documented, not automatically synced. A maintainer can create
them manually in GitHub from `.github/labels.yml`.

Later, the project can add a label-sync workflow. That should wait until the
public contribution flow is stable.
