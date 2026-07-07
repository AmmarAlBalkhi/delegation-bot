# Contributing

DelegationHQ is becoming mission control for agentic work. Contributions
should make AI delegation easier to inspect, approve, evaluate, and improve.

## Good First Contributions

Useful early contributions:

- fix documentation gaps
- add or improve evals
- add Harnessfile examples
- add adapter contract tests
- improve CLI output
- add playbooks for common AI workflows

Avoid starting with live execution adapters unless the dry-run contract and
ledger events are already clear.

See `docs/public-roadmap-issues.md` for curated public issue drafts and
`docs/issue-labels.md` for label rules. A good first issue should be small,
clear, local, and should not require secrets, model credits, or live GitHub
writes.

## Local Setup

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

## Required Checks

Run the full local QA suite before opening a pull request:

```bash
python scripts/qa.py
```

For packaging-sensitive changes, also smoke test:

```bash
delegation --help
python -m delegation_bot adapters codex.thread
```

## Design Rules

- Dry-run before live execution.
- Evidence before completion.
- Policies before tools.
- Keep the Harnessfile readable in pull requests.
- Keep adapter contracts small, explicit, and testable.
- Document durable decisions in `docs/decision-log.md`.

## Pull Requests

Each pull request should include:

- what changed
- why it matters
- how it was tested
- docs or schema updates when behavior changes

## Contribution License

Unless explicitly stated otherwise, contributions intentionally submitted to
this repository are submitted under the Apache License 2.0. See
`docs/license-strategy.md` for the project license decision.

The project does not require a separate Contributor License Agreement today.
DCO-style sign-offs are encouraged for outside contributions and may become
required before broad public launch:

```bash
git commit -s -m "Describe the change"
```

See `docs/contributor-license-policy.md` for the current policy notes.
