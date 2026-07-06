# Public Roadmap Issue Drafts

These are curated issue drafts for the public board. They are written so the
repository can look serious without becoming crowded or confusing.

Simple version:

```text
Open fewer issues.
Make each one sharp.
Every issue should strengthen the control-plane loop.
```

## Opening Rules

- Keep only a small set of roadmap issues open at once.
- Add acceptance criteria before asking for help.
- Prefer dry-run, no-network, fixture-backed work for early contributors.
- Use `good first issue` only when a newcomer can succeed without secrets,
  model credits, or live GitHub writes.
- Close stale roadmap issues when the plan changes.

## Draft 1: Policy Explanation Fixtures

Suggested title:

```text
Add policy explanation fixtures for explain-policy
```

Suggested labels:

docs, eval, trust-layer, roadmap
```

Body:

```markdown
## Goal

Add compact ledger fixtures and docs examples for `delegation explain-policy`.

## Why

The classifier explanation path is easier to understand when users can inspect
small low, medium, high, and blocked examples without running a full mission.

## Scope

- Add one or more local-classifier ledger fixtures.
- Show deterministic explanation output.
- Include an opt-in Ollama example without requiring it for tests.
- Keep model explanations non-authoritative.

## Acceptance criteria

- Fixtures cover at least low and high classifier outcomes.
- `delegation explain-policy --ledger <fixture>` works without network.
- Docs explain "model explains, gates decide" in simple language.
```

## Draft 2: Add Live Feedback Issue Comments Behind Approval

Suggested title:

```text
Add gated comments for feedback issue recovery
```

Suggested labels:

```text
eval, live-gate, trust-layer, roadmap
```

Body:

```markdown
## Goal

When an eval that previously failed starts passing, allow DelegationHQ to add
an approved recovery comment to the existing feedback issue.

## Why

The preview recovery draft exists. The next step is a live path that is still
explicit, approved, and auditable.

## Scope

- Add a `github.issue.comment` or equivalent approved live action design.
- Require explicit confirmation and repository policy checks.
- Record issue comment URL or id in the ledger.
- Keep issue closing separate from comment creation.

## Acceptance criteria

- Preview shows the exact comment before writing.
- Live mode requires explicit confirmation and token.
- Ledger records the resulting comment id or URL.
- Tests cover preview, blocked, and fake-client live paths.
```

## Draft 3: Design The GitHub App Installation Flow

Suggested title:

```text
Design GitHub App installation flow for DelegationHQ
```

Suggested labels:

```text
github-app, design, live-gate, roadmap
```

Body:

```markdown
## Goal

Design the future GitHub App installation flow for repository-scoped Delegation
Bot usage.

## Why

Personal tokens are okay for local development, but a real product needs scoped
installation, narrow permissions, webhooks, and clear trust boundaries.

## Scope

- Define read-only and issue-write installation modes.
- List minimum repository permissions.
- List first webhook events.
- Define how CLI and hosted dashboard should use installation tokens.
- Document safety rules before any app implementation begins.

## Acceptance criteria

- `docs/github-app-installation.md` describes permissions, webhooks, auth, and UX.
- The first implementation path remains dry-run first.
- No broad repository permissions are requested without a reason.
```

## Draft 4: Curate First Good-First Issues

Suggested title:

```text
Curate first good-first issues for adapters, evals, docs, and playbooks
```

Suggested labels:

```text
docs, good first issue, help wanted, roadmap
```

Body:

```markdown
## Goal

Create a small clean set of beginner-friendly issues that help contributors
improve DelegationHQ without touching live execution.

## Why

The project should feel ambitious but approachable. New contributors need clear
quests, not a maze.

## Scope

- Pick 3 to 5 beginner issues.
- Each issue should name the files likely to change.
- Each issue should include a QA command.
- Each issue should explain how it strengthens the control-plane loop.

## Acceptance criteria

- No good-first issue requires secrets, network calls, or paid model access.
- Every good-first issue has a clear done state.
- Labels match `docs/issue-labels.md`.
```

## Draft 5: Add A Shell Dry-Run Adapter Contract

Suggested title:

```text
Add shell.command dry-run adapter contract
```

Suggested labels:

```text
adapter, design, roadmap
```

Body:

```markdown
## Goal

Add a dry-run `shell.command` adapter contract for local command plans without
executing them.

## Why

A lot of agent work eventually reaches shell commands. DelegationHQ should
make command intent, working directory, environment needs, and risk visible
before anything executes.

## Scope

- Add adapter contract metadata.
- Add SDK-backed dry-run adapter output and evidence.
- Detect write, network, secret, and destructive-looking command risk.
- Add one fixture and focused tests.

## Acceptance criteria

- Dry-run never executes a command.
- Evidence includes command preview, working directory, risk level, and
  recommended gate.
- Docs show how this strengthens the control-plane loop.
```

## Draft 6: Read-Only Hosted Dashboard Prototype

Suggested title:

```text
Prototype read-only dashboard for ledgers and Harnessfiles
```

Suggested labels:

```text
design, trust-layer, roadmap
```

Body:

```markdown
## Goal

Prototype a read-only dashboard that can show a Harnessfile, dry-run plan,
ledger evidence, eval status, and promotion state.

## Why

CLI is the engine. Dashboard is the cockpit. Users should see proof without
reading raw JSON first.

## Scope

- Read local or uploaded ledger files.
- Show mission, plan, ledger, evals, agents, and playbooks.
- No live GitHub writes.
- No model calls.
- No agent execution.

## Acceptance criteria

- Dashboard prototype uses fixture data.
- Every blocked state shows a next safe action.
- Raw JSON remains available.
- UI follows `docs/dashboard-wireframe.md`.
```
