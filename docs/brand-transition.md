# DelegationHQ Brand Transition

DelegationHQ is the public brand and package identity.

The product promise stays the same:

```text
Mission control for agentic work.
```

## What Changes Now

- Public name: `DelegationHQ`
- Python distribution name: `delegationhq`
- Future repository name: `AmmarAlBalkhi/delegationhq`
- Primary domain target: `delegationhq.ai`
- Developer domain target: `delegationhq.dev`
- Windows install directory: `%LOCALAPPDATA%\DelegationHQ\bin`

## What Stays Stable

- CLI command: `delegation`
- Python import namespace: `delegation_bot`
- Local source wrapper: `python scripts/delegation.py`
- Package module entry point: `python -m delegation_bot`
- Harnessfile protocol word: `delegation`

This keeps user muscle memory stable while the public brand gets stronger.

## Compatibility Rules

Do not rename the Python import namespace before `1.0` unless there is a clear
migration plan. Import churn makes the project feel unstable and does not help
new users.

Do not change ledger markers such as `delegation-bot:eval:...` in old fixtures.
Those markers are historical evidence and duplicate-detection keys. A future
schema version can add `delegationhq:` markers with compatibility parsing.

Use `DelegationHQ` in README, release, install, package, and website-facing
docs. Older architecture notes may keep historic wording until they are touched
for product work.

## Trademark And Domain Notes

Buying a domain does not create trademark rights by itself. Before a serious
commercial launch, the maintainer should:

- keep dated evidence of public use
- do a deeper trademark search
- file `DELEGATIONHQ` as a word mark when the product is ready
- keep renewal reminders for `delegationhq.ai` and `delegationhq.dev`

Simple version: buy early, use clearly, file before the product becomes loud.
