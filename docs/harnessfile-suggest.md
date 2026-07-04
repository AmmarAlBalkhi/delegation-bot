# Harnessfile Suggest

`delegation suggest` is the no-blank-page entry point.

It turns a plain-language goal into a draft Harnessfile, then routes that draft
through the same deterministic validation, planning, and ledger path as any
hand-written Harnessfile.

```text
user goal -> suggested Harnessfile -> validation -> dry-run plan -> ledger
```

## Why It Exists

The control plane should not make users write a large YAML file before they see
value. A user should be able to start with:

```bash
delegation suggest "prepare this repo for release"
```

The first implementation is template-backed and no-network. It does not call a
live LLM. That is intentional: the command proves the product shape while
keeping the trust boundary crisp.

## Trust Boundary

`delegation suggest` follows the hybrid model:

```text
AI proposes.
Delegation Bot verifies.
Human approves risky actions.
Ledger records everything.
Evals decide whether trust increases.
```

Today, the "AI proposes" slot is represented by safe templates and CLI intent.
Later, a model-backed drafting mode can be added behind explicit configuration,
but it should still output a normal Harnessfile that the deterministic control
plane must validate and dry-run.

## Usage

Write a suggested Harnessfile and immediately compile its dry-run plan:

```bash
delegation suggest "prepare this repo for release" \
  --output .delegation/suggested-release.yaml \
  --plan \
  --ledger .delegation/suggested-release.jsonl
```

Print only the suggested YAML:

```bash
delegation suggest "refresh the README docs" --yaml
```

Force a template:

```bash
delegation suggest "prepare launch notes" --template release-readiness
```

## Current Templates

- `release-readiness`
- `ci-repair`
- `documentation-refresh`
- `code-review`
- `weekly-planning`
- `general-agentic-work`

The template is inferred from the goal unless `--template` is provided.

## Product Standard

Good suggestions should:

- produce valid Harnessfiles
- prefer safe dry-run adapters
- include human approval for risky work
- leave a ledger when planned
- explain the selected template
- give the user a next command

Suggestions are never trusted execution. They are a faster path into the trust
loop.
