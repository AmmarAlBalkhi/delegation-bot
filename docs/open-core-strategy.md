# Open-Core Strategy

DelegationHQ should be useful as open source and disciplined about what becomes
public.

## Public Core

The public repository should make the core trust loop easy to understand and
easy to run:

```text
Harnessfile -> dry-run plan -> policy gates -> adapter actions -> run ledger -> evals -> promotion
```

Keep public:

- Harnessfile validation and schemas
- dry-run planning
- adapter contracts and SDK examples
- local run ledger format
- approval gates
- basic evals
- playbooks and fixtures
- install, release, and QA docs
- safe demos that do not need secrets

This gives users real value without needing a hosted service.

## Private Until Ready

Some work should stay outside the public repo until it is mature, safe to share,
or intentionally productized:

- proprietary ranking or routing logic
- private eval packs
- hosted service implementation details
- billing, account, and customer operations
- private adapter work
- unreleased integrations
- sensitive launch planning

No secrets, customer data, credentials, or private strategy should be committed
to the public repository.

## Publishing Checklist

Before moving local work into a public branch:

- the demo path is clear
- tests and QA pass
- docs explain user value without exposing private implementation strategy
- examples do not require secrets or paid accounts
- live actions remain gated by dry-run, confirmation, and evidence
- package metadata points only to locations the project controls

Simple version:

```text
Public repo: useful engine and clear story.
Private work: unfinished edge, business logic, and sensitive plans.
```
