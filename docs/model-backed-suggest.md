# Model-Backed Harnessfile Suggest

`delegation suggest` has three paths:

- `template`: default, no-network, deterministic
- `fixture`: no-network saved model draft for tests and demos
- `model`: explicit live provider call

Simple version:

```text
goal -> model draft -> schema envelope -> Harnessfile validation -> dry-run plan -> ledger
```

The model helps the user start. It does not decide what is trusted.

## Product Rule

Model-backed suggestions must be explicit opt-in.

The default command remains no-network and template-backed:

```bash
delegation suggest "prepare this repo for release"
```

Live model-backed suggestions require a provider and a second confirmation
flag:

```bash
delegation suggest "prepare this repo for release" \
  --draft-source model \
  --provider openai \
  --allow-live-model \
  --output .delegation/model-openai-release.yaml \
  --plan \
  --ledger .delegation/model-openai-release.jsonl
```

or:

```bash
delegation suggest "review this pull request" \
  --draft-source model \
  --provider anthropic \
  --allow-live-model \
  --output .delegation/model-anthropic-review.yaml \
  --plan \
  --ledger .delegation/model-anthropic-review.jsonl
```

or local Ollama:

```bash
delegation suggest "prepare this repo for safe AI delegation" \
  --draft-source model \
  --provider ollama \
  --allow-live-model \
  --model llama3.2 \
  --output .delegation/model-ollama-safe-delegation.yaml \
  --plan \
  --ledger .delegation/model-ollama-safe-delegation.jsonl
```

No hidden model calls. No surprise cost. No surprise data sharing.

Required environment variables:

- OpenAI: `OPENAI_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY` or `CLAUDE_API_KEY`
- Ollama: no API key; defaults to `http://localhost:11434`

If a hosted-provider key is missing, the command fails before any provider call.
For Ollama, use `--base-url` or `OLLAMA_HOST` when the local server is not on
the default host.

## Ease-Of-Use Rule

Plain `delegation suggest "goal"` stays short. It prints a summary and next
command, not a wall of YAML.

Use `--output` to write a Harnessfile. Use `--yaml` only when you want the full
Harnessfile in the terminal.

Caveman version:

```text
AI drafts.
Bot checks.
No key, no call.
No approval, no live action.
```

## No-Network Fixture Mode

The project has fixture-backed model drafts for testing provider paths without
calling any model API:

```bash
delegation suggest "prepare this repo for release" --draft-source fixture --provider openai --output .delegation/model-openai-release.yaml --plan --ledger .delegation/model-openai-release.jsonl
delegation suggest "review this pull request" --draft-source fixture --provider anthropic --output .delegation/model-anthropic-review.yaml --plan --ledger .delegation/model-anthropic-review.jsonl
```

These fixtures live in `examples/model-suggestions/`.

They are not live model calls. They are saved draft envelopes that prove the
schema, validation, planning, and ledger loop works without cost or network.

## Trust Boundary

The model may:

- propose a Harnessfile
- explain why it picked agents, adapters, evals, and approvals
- suggest safer defaults
- point out missing context

The model must not:

- approve its own plan
- execute adapters
- mark evals as passed
- promote agents
- bypass policy gates
- write ledgers directly

The control plane still owns:

- Harnessfile validation
- dry-run compilation
- policy gates
- approval requirements
- ledger events
- eval results
- promotion decisions

## Provider Shape

OpenAI path:

- uses the Responses API
- requests a `harness-suggestion-draft` envelope
- validates the returned `manifest` with the normal Harnessfile validator
- rejects invalid drafts before planning

Anthropic path:

- uses the Messages API
- treats JSON text or tool-use input as the draft envelope
- validates the returned `manifest` with the normal Harnessfile validator
- rejects invalid drafts before planning

Local model path:

- uses Ollama's `/api/generate` endpoint
- requests `stream: false` and JSON mode
- uses the same draft envelope as hosted providers
- is designed for privacy-sensitive drafting on local infrastructure
- still uses deterministic validation before the draft becomes a plan

## Draft Envelope

The model should return the shape defined in:

```text
schemas/harness-suggestion-draft.v1.schema.json
```

That envelope includes:

- the original goal
- draft source
- provider and model
- rationale
- proposed Harnessfile manifest
- safety notes
- validation expectations

The envelope is not a ledger event. It is only input to validation.

## Failure Rules

If the model returns invalid JSON:

- show a short error
- suggest falling back to the template-backed command
- do not write a Harnessfile

If the draft envelope is valid but the Harnessfile is invalid:

- show the Harnessfile validation errors
- do not compile a plan
- do not write a ledger

If the Harnessfile validates:

- write the suggested Harnessfile if `--output` is present
- compile the dry-run plan if `--plan` is present
- write the ledger only from deterministic planning, never from the model

## Prompt Contract

The system prompt is intentionally strict:

```text
You draft Delegation Bot Harnessfiles.
Return only one JSON object.
Prefer dry-run adapters.
Require human approval for risky actions.
Do not claim execution happened.
Do not mark evals passed.
Do not include secrets.
```

The user message includes:

- plain-language goal
- repository
- owner
- provider and model
- template hint
- valid reference manifest
- required draft envelope shape

## Current Acceptance

Model-backed suggest is considered safe for early use because:

1. It is off by default.
2. Live calls require `--allow-live-model`.
3. OpenAI, Anthropic, and Ollama use the same draft envelope.
4. Fixture mode remains no-network for tests.
5. Invalid model output cannot create a plan.
6. Valid model output still goes through `validate`, `plan`, ledger, evals, and promotion.
7. The README explains cost and data-sharing plainly.

## Research Notes

Checked on 2026-07-05:

- OpenAI Responses API is the request path used for live OpenAI suggestions:
  <https://platform.openai.com/docs/api-reference/responses/create>
- Anthropic Messages API is the request path used for Claude suggestions:
  <https://docs.anthropic.com/en/api/messages>
- Ollama `/api/generate` is the local request path used for local suggestions,
  with `stream: false` and JSON mode:
  <https://github.com/ollama/ollama/blob/main/docs/api.md>
