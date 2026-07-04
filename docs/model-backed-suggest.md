# Model-Backed Harnessfile Suggest

This is the design for the future model-backed version of `delegation suggest`.

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

A future model-backed command should look explicit:

```bash
delegation suggest "prepare this repo for release" --draft-source model --provider openai
```

or:

```bash
delegation suggest "review this pull request" --draft-source model --provider anthropic
```

No hidden model calls. No surprise cost. No surprise data sharing.

## No-Network Fixture Mode

The project now has fixture-backed model drafts for testing the future provider
paths without calling any model API:

```bash
delegation suggest "prepare this repo for release" --draft-source fixture --provider openai --output .delegation/model-openai-release.yaml --plan --ledger .delegation/model-openai-release.jsonl
delegation suggest "review this pull request" --draft-source fixture --provider anthropic --output .delegation/model-anthropic-review.yaml --plan --ledger .delegation/model-anthropic-review.jsonl
```

These fixtures live in `examples/model-suggestions/`.

They are not live model calls. They are saved draft envelopes that prove the
schema, validation, planning, and ledger loop works before real provider calls
are added.

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

- use structured outputs so the draft follows a known JSON shape
- request a `harness-suggestion-draft` envelope
- validate the returned `manifest` with the normal Harnessfile validator
- reject or repair invalid drafts before planning

Anthropic path:

- use Messages API tool use with an `input_schema`
- define one client tool such as `propose_harnessfile`
- treat returned `tool_use` input as the draft envelope
- validate the returned `manifest` with the normal Harnessfile validator

Local model path:

- use the same draft envelope
- prefer local models for privacy-sensitive policy review or rough drafts
- require deterministic validation before the draft becomes a plan

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
- do not write a Harnessfile unless `--output-invalid` exists later

If the draft envelope is valid but the Harnessfile is invalid:

- show the Harnessfile validation errors
- do not compile a plan
- optionally write the invalid draft only when the user asks for debugging

If the Harnessfile validates:

- write the suggested Harnessfile if `--output` is present
- compile the dry-run plan if `--plan` is present
- write the ledger only from deterministic planning, never from the model

## Prompt Contract

The system prompt should be boring and strict:

```text
You draft Delegation Bot Harnessfiles.
Return only the requested structured draft envelope.
Prefer dry-run adapters.
Require human approval for risky actions.
Do not claim execution happened.
Do not mark evals passed.
Do not include secrets.
```

The user message should include:

- plain-language goal
- repository
- owner
- allowed adapters
- allowed files if known
- whether the user wants release, CI, docs, review, planning, or general work

## MVP Acceptance

Model-backed suggest is ready only when:

1. It is off by default.
2. It supports at least OpenAI and Anthropic through the same draft envelope.
3. It can run in a no-network fixture mode for tests. The first fixture mode is now implemented.
4. Invalid model output cannot create a plan.
5. Valid model output still goes through `validate`, `plan`, ledger, evals, and promotion.
6. The README explains cost and data-sharing plainly.

## Research Notes

Checked on 2026-07-04:

- OpenAI Structured Outputs are intended for model responses that follow a JSON schema:
  <https://developers.openai.com/api/docs/guides/structured-outputs>
- OpenAI Responses API can generate JSON outputs and call tools:
  <https://developers.openai.com/api/reference/resources/responses/methods/create/>
- Anthropic Claude tool use supports tools with an `input_schema`, returning a structured
  `tool_use` block for the application to execute:
  <https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview>
- Anthropic Messages API remains the base request path for Claude applications:
  <https://docs.anthropic.com/en/api/messages>
