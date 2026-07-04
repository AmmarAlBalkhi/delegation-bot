# Product Experience

Trust should reduce anxiety, not create chores.

Delegation Bot can be serious infrastructure and still feel light to use. The
experience goal is:

```text
Useful in 60 seconds.
Powerful after 10 minutes.
Deep only when the user asks for depth.
```

## Experience Promise

Users should not have to understand the whole control plane before getting
value. The first run should show a clear plan, a ledger, and eval results with
safe defaults.

The product should feel like:

- "I can see what the AI would do before it does it."
- "I can start from a playbook instead of a blank file."
- "AI can draft the plan for me."
- "The tool tells me what is blocked and how to unblock it."
- "Evidence is summarized first, with details available when I need them."

## Low-Friction Rules

1. Start from a goal, playbook, or example, not a blank schema.
2. Prefer one useful command over many setup steps.
3. Use progressive disclosure: summary first, details on demand.
4. Let AI draft Harnessfiles, issue bodies, summaries, and fixes.
5. Keep deterministic checks strict, but make their messages helpful.
6. Give every blocked state a next action.
7. Avoid approval spam; ask for approval only when risk justifies it.
8. Do not make users read walls of JSON to understand the run.
9. Keep the safe path obvious and the risky path explicit.
10. Make ledgers inspectable without making users feel audited by default.

## First-Run Path

The public experience should move toward this:

```text
delegation suggest "prepare this repo for release"
delegation plan Harnessfile.yaml
delegation eval Harnessfile.yaml --ledger .delegation/latest.jsonl --write
delegation promote Harnessfile.yaml --ledger .delegation/latest.jsonl
```

Until `delegation suggest` exists, playbooks are the no-blank-page path:

```text
delegation catalog
delegation plan playbooks/release-readiness.yaml --ledger .delegation/latest.jsonl
```

## Anti-Patterns

Avoid:

- making users write large YAML files before seeing value
- asking for fields the tool can infer or suggest
- showing policy language before showing the plan
- hiding simple outcomes behind abstract terminology
- making safe dry-runs feel like compliance work
- adding dashboards before the CLI loop feels clear
- treating every action as equally risky

## Product Test

Before adding a feature, ask:

```text
Does this make trustworthy AI delegation faster, clearer, or easier?
```

If it adds safety but also adds friction, pair it with a shortcut, template,
plain-English explanation, or AI-assisted draft.
