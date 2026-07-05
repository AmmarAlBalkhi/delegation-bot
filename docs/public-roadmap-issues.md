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

## Draft 1: Opt-In Live Model-Backed Harnessfile Suggestions

Suggested title:

```text
Add opt-in live model-backed delegation suggest
```

Suggested labels:

```text
enhancement, trust-layer, live-gate, roadmap
```

Body:

```markdown
## Goal

Allow `delegation suggest` to use a live model provider when the user explicitly
opts in, while keeping validation, dry-run planning, ledgers, evals, and human
approval deterministic.

## Why

Users should not start from a blank Harnessfile. AI can draft the mission, but
Delegation Bot must still verify it before anything executes.

## Scope

- Add explicit provider configuration.
- Require an opt-in flag for live model calls.
- Keep fixture mode as the default test path.
- Validate model output against `schemas/harness-suggestion-draft.v1.schema.json`.
- Refuse to run if required secrets are missing.
- Never apply live actions from model output directly.

## Acceptance criteria

- `delegation suggest --draft-source model --provider openai` is gated and documented.
- Anthropic path has the same contract shape.
- Fixture tests remain no-network.
- Bad model output fails with a clear validation error.
- Docs explain the trust boundary in simple language.
```

## Draft 2: Link Feedback Drafts To Live GitHub Issue Numbers

Suggested title:

```text
Track live GitHub issue numbers for eval feedback drafts
```

Suggested labels:

```text
eval, live-gate, trust-layer, roadmap
```

Body:

```markdown
## Goal

When a feedback draft is applied through `delegation apply-issues`, record the
live GitHub issue number and URL in the ledger so future eval failures can
update the right issue.

## Why

The feedback loop should improve the project without creating duplicate issue
noise.

## Scope

- Extend applied `github.issue` ledger evidence with issue number and URL.
- Teach feedback grouping to prefer existing live issue links when present.
- Keep preview mode readable before any write.
- Add fixture coverage for applied and updated issue states.

## Acceptance criteria

- Preview still works without a token.
- Apply mode writes issue metadata into the ledger.
- Repeated failures point to the existing issue.
- Tests cover draft, applied, and update paths.
```

## Draft 3: Design The GitHub App Installation Flow

Suggested title:

```text
Design GitHub App installation flow for Delegation Bot
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
improve Delegation Bot without touching live execution.

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

## Draft 5: Add A Real-World Adapter Candidate Matrix

Suggested title:

```text
Add real-world adapter candidate matrix
```

Suggested labels:

```text
adapter, design, roadmap
```

Body:

```markdown
## Goal

Prioritize the next adapter contracts by user value, implementation risk, and
trust evidence.

## Why

Delegation Bot should become a harness for AI harnesses, but not by adding
random integrations. The next adapters should prove real workflows.

## Candidate areas

- Slack or Discord notifications
- Linear or Jira issues
- shell command dry-run adapter
- CrewAI or AutoGen harness adapter
- local model provider adapter

## Acceptance criteria

- Matrix includes user value, risk, required evidence, approvals, and first eval.
- At least one candidate is marked suitable for a no-network first implementation.
- Docs explain why each candidate matters.
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
