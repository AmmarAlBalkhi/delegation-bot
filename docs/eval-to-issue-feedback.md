# Eval-To-Issue Feedback Loop

The feedback loop turns failed evidence into better future behavior.

Simple version:

```text
ledger event -> eval result -> dedupe marker -> GitHub Issue draft -> playbook or regression eval
```

This should start as dry-run planning, not automatic issue spam.

## Why It Matters

Delegation Bot should improve through use. When a run fails, the system should
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

Phase 3:

- link the generated issue back to the failed run
- close or update the issue when the eval later passes
- report recurring failures as playbook or adapter reliability signals

## Policy

Default policy:

- failed evals may draft issues
- blocked evals may draft issues only when the block repeats
- issue creation requires explicit apply mode or human approval
- issue bodies must not include secrets, full prompts with secrets, or raw model
  responses unless sanitized

## First Implementation Slice

The first code slice is now implemented through:

```bash
python scripts/delegation.py feedback examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl --include-blocked
```

What it does:

- reads `eval.result` events from the ledger
- drafts dry-run GitHub Issues for failed evals
- optionally includes blocked evals with `--include-blocked`
- redacts obvious secret-like fields from failure details
- groups repeated eval failures by deterministic marker
- marks drafts as `create` or `update` based on repeated failures or existing
  feedback events
- uses the existing `github.issue` adapter to emit planned issue evidence
- can append planned feedback issue events with `--write`

The next implementation slice should be:

1. Add a function that converts `EvalResult` into a `github.issue` adapter
   request for direct eval-result objects, not only ledger events.
2. Add repeat-threshold policy for blocked evals.
3. Link dry-run update drafts to live GitHub issue numbers after apply mode
   exists.
4. Keep live GitHub writes behind the existing apply mode.

This keeps the project aligned with its own rule: evidence first, then action.
