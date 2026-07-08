# Product Experience

Trust should reduce anxiety, not create chores.

DelegationHQ can be serious infrastructure and still feel light to use. The
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

DelegationHQ is not a generic agent launcher, a personal assistant, or a fake
demo dashboard. It is a working trust cockpit for agentic work.

The first product slice should work on real local projects:

```text
open DelegationHQ -> add agent -> assign workspace -> define scope -> preview risk
-> approve/block -> record evidence -> ingest ledger -> review timeline/status
```

The product should feel like:

- "I can see what the AI would do before it does it."
- "I can start from a playbook instead of a blank file."
- "AI can draft the plan for me."
- "The tool tells me what is blocked and how to unblock it."
- "Evidence is summarized first, with details available when I need them."
- "This agent wants to do something. I can see the risk and approve only if it
  makes sense."

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

The public experience should move toward fewer visible flows that actually
work:

```text
workspace-init -> agent-add -> approval-preview/agent-gate -> approval-decision
-> agent-result-ingest/evidence-ingest/runprint-ingest -> timeline -> eval/promotion
```

`delegation demo` should stay install-safe and useful without network access.
`delegation init` should create a starter Harnessfile without making users write
YAML from scratch.

`delegation suggest` now exists as a no-network, template-backed first version.
Plain suggest output should stay short; full YAML is available with `--yaml` or
`--output`.

Live model-backed suggest is allowed only when the user explicitly opts in:

```text
delegation suggest "prepare this repo for release" --draft-source model --provider openai --allow-live-model
delegation suggest "prepare this repo for safe AI delegation" --draft-source model --provider ollama --allow-live-model
```

Playbooks remain another no-blank-page path:

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
- showing app panels that are not backed by real local state
- over-compressing the product into GitHub/code only
- making RunPrint feel like the whole product instead of one evidence tool
- treating every action as equally risky
- making people install Python packaging tools before they understand the demo

## Product Areas

The app/cockpit should stay focused on real, functional areas:

- Agents
- Missions
- Approval Inbox
- Evidence
- Timeline
- Settings

Evidence tools are plural. RunPrint is the current recorder/evidence agent, but
DelegationHQ is bigger: future tools can record diffs, tests, CRM changes,
research artifacts, browser sessions, API calls, logs, or business workflow
proof under the same control loop.

Approval Preview should keep the human decision simple while exposing the
action intent underneath: execution mode, likely touched resources, live effect,
required confirmation, command preview, expected proof, and the exact question
the user is answering.

## Product Test

Before adding a feature, ask:

```text
Does this make trustworthy AI delegation faster, clearer, or easier?
```

The future Windows `.exe` should serve that same test: faster first run, same
trust gates.

If it adds safety but also adds friction, pair it with a shortcut, template,
plain-English explanation, or AI-assisted draft.

## Approval Preview Feeling

Agent gates should not feel like policy paperwork.

Good:

```text
This agent wants to edit 3 files and open a PR.
Risk: low.
Required evidence: diff, tests, ledger.
Approve?
```

Good:

```text
This CRM agent wants to update customer records.
Risk: medium.
Human approval required.
```

Bad:

```text
Please configure 40 policy fields before previewing this action.
```
