# Eval-To-Issue Feedback Loop

The feedback loop turns failed evidence into better future behavior.

Simple version:

```text
ledger event -> eval result -> dedupe marker -> GitHub Issue draft -> live issue memory -> playbook or regression eval
```

Even simpler now:

```text
eval result -> feedback issue draft
```

This should start as dry-run planning, not automatic issue spam.

## Why It Matters

DelegationHQ should improve through use. When a run fails, the system should
not only say "failed." It should preserve enough evidence for a human or agent
to create a focused improvement issue.

Good failures become:

- regression evals
- adapter contract fixes
- playbook updates
- policy changes
- documentation fixes

## Trigger

The first trigger should be an `eval.result` ledger event with status `failed`
or `blocked`.

The lower-friction trigger is a direct `EvalResult` object from the current
`delegation eval` run. That lets the CLI draft feedback without requiring
`eval --write` first.

Important fields:

- `details.eval_id`
- `details.eval.status`
- `details.eval.message`
- `details.eval.details`
- `run_id`
- `sequence`
- source Harnessfile path

## Issue Dedupe

Every generated issue draft should include a deterministic marker:

```text
<!-- delegation-bot:eval:<eval_id>:<hash> -->
```

The hash should include:

- repository
- Harnessfile id
- eval id
- normalized failure details

That keeps recurring failures visible without creating duplicates every run.

If a feedback issue has already been applied live, the ledger preserves the
GitHub issue number and URL. Future matching failures become update drafts that
point at the same issue instead of creating a fresh one.

## Draft Issue Shape

Title:

```text
Eval failed: <eval_id>
```

Body:

````markdown
<!-- delegation-bot:eval:<eval_id>:<hash> -->

## What Failed

<eval message>

## Ledger Evidence

- run_id:
- sequence:
- status:
- source ledger:

## Repeat Signal

- planned operation:
- matching eval occurrences in this ledger:
- existing feedback events in this ledger:
- existing live issue events in this ledger:
- live GitHub issue:

## Failure Details

```json
{}
```

## Suggested Fix

- [ ] decide whether this is a product bug, docs gap, adapter gap, or playbook gap
- [ ] add or update a regression eval
- [ ] update the affected adapter, playbook, policy, or documentation
- [ ] rerun `python scripts/qa.py`
````

## Adapter Path

The feedback loop should use the existing `github.issue` adapter contract.

Phase 1:

- render the issue draft locally
- include the dedupe marker
- write a `github.issue.planned` ledger event
- do not write to GitHub

Phase 2:

- require approval for issue creation on scheduled runs
- allow manual `workflow_dispatch` apply mode
- add the artifact URL or ledger path to the issue body
- record the live GitHub issue number and URL after apply

Phase 3:

- close or update the issue when the eval later passes
- report recurring failures as playbook or adapter reliability signals

## Policy

Default policy:

- failed evals may draft issues
- blocked evals may draft issues only when the block repeats
- issue creation requires explicit apply mode or human approval
- issue bodies must not include secrets, full prompts with secrets, or raw model
  responses unless sanitized

The default blocked repeat threshold is `2`. That means a single blocked eval is
reported in the eval output, but it does not become a feedback issue draft until
the same block appears twice in the ledger. Users can opt into immediate blocked
drafts with:

```bash
python scripts/delegation.py feedback Harnessfile.yaml \
  --ledger .delegation/latest.jsonl \
  --include-blocked \
  --blocked-repeat-threshold 1
```

## First Implementation Slice

The first code slice is now implemented through:

```bash
python scripts/delegation.py feedback examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl --include-blocked
```

The direct eval-result slice is now implemented through:

```bash
python scripts/delegation.py eval examples/ai-harness-control-plane.yaml \
  --ledger .delegation/latest.jsonl \
  --feedback \
  --feedback-include-blocked
```

What it does:

- reads `eval.result` events from the ledger
- drafts dry-run GitHub Issues for failed evals
- optionally includes repeated blocked evals with `--include-blocked`
- redacts obvious secret-like fields from failure details
- groups repeated eval failures by deterministic marker
- marks drafts as `create` or `update` based on repeated failures or existing
  feedback events
- reuses live GitHub issue numbers and URLs from prior apply events
- uses the existing `github.issue` adapter to emit planned issue evidence
- can append planned feedback issue events with `--write`
- can now draft feedback directly from current `EvalResult` objects with
  `eval --feedback`
- can append planned feedback issue events directly with `eval --feedback-write`

Inspect the feedback memory fixture without touching GitHub:

```bash
python scripts/delegation.py ledger examples/ledgers/feedback-issue-memory.jsonl --adapter github.issue
```

## Recovery Drafts

When an eval passes after a prior live feedback issue exists, DelegationHQ can
draft a recovery update:

```bash
python scripts/delegation.py recover-feedback Harnessfile.yaml \
  --ledger .delegation/latest.jsonl
```

This command is preview-only unless `--write` is supplied. It does not close the
GitHub issue by itself. It drafts the evidence a human or future approved live
gate can use to close or update the issue.

Inspect the recovery fixture:

```bash
python scripts/delegation.py ledger examples/ledgers/feedback-recovery.jsonl --adapter github.issue
python scripts/delegation.py dashboard examples/ledgers/feedback-recovery.jsonl
```

## Live Feedback Apply

After recovery drafts exist, preview the live GitHub action:

```bash
python scripts/delegation.py apply-feedback Harnessfile.yaml \
  --ledger .delegation/latest.jsonl
```

Preview mode never writes to GitHub. A live comment requires the exact
confirmation token:

```bash
GITHUB_TOKEN=... python scripts/delegation.py apply-feedback Harnessfile.yaml \
  --ledger .delegation/latest.jsonl \
  --apply \
  --confirm LIVE_FEEDBACK_ISSUES
```

With GitHub App issue-write auth configured, use:

```bash
python scripts/delegation.py apply-feedback Harnessfile.yaml \
  --ledger .delegation/latest.jsonl \
  --apply \
  --confirm LIVE_FEEDBACK_ISSUES \
  --auth github-app
```

Closing the issue is a stronger action and uses a different confirmation:

```bash
GITHUB_TOKEN=... python scripts/delegation.py apply-feedback Harnessfile.yaml \
  --ledger .delegation/latest.jsonl \
  --apply \
  --close \
  --confirm CLOSE_FEEDBACK_ISSUES
```

This command comments on the existing live feedback issue with the recovery
evidence. With `--close`, it closes the issue after the comment succeeds. Both
paths append ledger events with the comment URL, issue number, marker, and
feedback lifecycle state.

This keeps the project aligned with its own rule: evidence first, then action.
