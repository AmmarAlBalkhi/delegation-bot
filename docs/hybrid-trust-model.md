# Hybrid Trust Model

Delegation Bot should be AI-enabled, not AI-governed.

The core rule:

```text
AI proposes.
Delegation Bot verifies.
Human approves risky actions.
Ledger records everything.
Evals decide whether trust increases.
```

This is the product's trust boundary. AI can be creative, fast, and useful, but
the control plane must stay inspectable and repeatable.

## Why Hybrid

If the same AI that does the work also decides whether the work is safe, the
system loses trust. The model can be wrong, inconsistent, overconfident, or
fooled by prompt injection.

Delegation Bot should solve that by separating two jobs:

- AI helps create plans, explanations, suggestions, drafts, and work products.
- Deterministic code decides policy gates, required evidence, ledger shape,
  eval results, and promotion readiness.

That split lets the project enable bigger AI work without making safety vague.

## What AI Should Do

AI is allowed and encouraged to help with:

- drafting Harnessfiles from natural-language goals
- recommending adapters and harnesses
- estimating risk and required approvals
- explaining dry-run plans in plain English
- summarizing run ledgers
- proposing fixes when evals fail
- writing issue bodies, PR descriptions, and release notes
- comparing model or harness options

The first product surface for this should be a `delegation suggest` flow:

```text
user goal -> AI-drafted Harnessfile -> deterministic validation -> dry-run plan
```

## What Deterministic Code Should Control

The control layer should decide:

- whether the Harnessfile is valid
- which actions are allowed or blocked
- which actions require human approval
- what evidence is required before completion
- what gets written to the ledger
- whether evals passed, failed, or blocked
- whether an agent earns more autonomy

These decisions should be reproducible. The same inputs should produce the same
control-plane decision.

## Design Test

Before adding a feature, ask:

1. Does this make AI more useful?
2. Does the deterministic layer still verify the plan?
3. Does a human still approve risky actions?
4. Does the ledger preserve evidence?
5. Do evals, not vibes, decide whether trust increases?

If the answer is yes, the feature fits the product.

If AI is being asked to approve itself, mark the feature risky and redesign the
boundary.

## Product Memory

Keep this principle visible in the README, positioning, architecture, roadmap,
and active next-action queue. It is how the project stays focused while adding
LLMs, models, agent frameworks, live adapters, dashboards, and paid surfaces.
