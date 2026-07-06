# Million-Star Strategy

This is an ambition map, not a traction claim. The goal is not to fake
popularity; the goal is to build something useful enough that legitimate
adoption can compound over time.

## Positioning

DelegationHQ should own a category, not just a feature.

Category name:

```text
AI delegation control plane
```

Plain-language version:

```text
Mission control for agentic work.
```

The project should become the thing people put above their agent frameworks:

- OpenAI Agents SDK for agent execution
- Anthropic Claude for model calls and tool use
- Claude Code for coding-agent execution
- LangGraph for durable workflows
- GitHub Actions for automation
- MCP for tools
- Codex for software work
- DelegationHQ for planning, policy, evidence, ledgers, evals, and governance

Keep the deeper category and uniqueness framing in `docs/positioning.md`.

## Audience

### Primary Users

AI builders who already have agents or automations and now need control:

- solo builders shipping AI tools
- open-source maintainers using coding agents
- startup engineering leads trying to make agent work auditable
- platform engineers building internal AI automation
- researchers comparing agent harnesses

### Primary Pain

The pain is not "I need another agent."

The pain is:

- I do not know what the agent is about to do.
- I cannot compare runs across frameworks.
- I cannot prove what happened.
- I cannot enforce human approval consistently.
- I cannot turn mistakes into evals.
- I cannot safely share repeatable agent workflows.

## Product Promise

DelegationHQ should promise:

```text
Plan it once. Dry-run it. Approve it. Execute anywhere. Learn from every run.
```

That sentence should shape the CLI, docs, examples, and launch demo.

One more product promise matters:

```text
Give agents more power as they prove themselves.
```

## Product Surface

### CLI

Future command shape:

```bash
delegation validate Harnessfile.yaml
delegation plan Harnessfile.yaml --ledger .delegation/latest.jsonl
delegation adapters
delegation run Harnessfile.yaml --dry-run
delegation ledger show .delegation/latest.jsonl
delegation eval Harnessfile.yaml --ledger .delegation/latest.jsonl --write
delegation promote Harnessfile.yaml --ledger .delegation/latest.jsonl
```

The repository currently exposes this through `python scripts/delegation.py`
while packaging is still intentionally simple.

The first package step exposes the same CLI as an installable command:

```bash
python -m pip install -e .
delegation --help
python -m delegation_bot adapters codex.thread
```

### GitHub Action

The GitHub Action should be the default adoption path:

```yaml
- uses: AmmarAlBalkhi/delegationhq@v1
  with:
    harnessfile: Harnessfile.yaml
    apply: false
```

### Manifest

The Harnessfile is the product's contract. It must stay:

- readable
- portable
- reviewable in pull requests
- strict enough for policy
- flexible enough for adapters

It should describe models, agent passports, capability packs, and promotion
rules, not just executors.

### Ledger

The run ledger is the trust engine. Every adapter action should emit an event:

- planned
- skipped
- blocked
- approved
- executed
- verified
- failed

### Evals

Evals turn operations into learning. The first built-in evals should be boring
and powerful:

- no duplicate issues
- all required approvals exist
- all required evidence exists
- tests pass before pull request
- ledger is internally consistent

## Launch Narrative

The launch should show one story:

1. "Here is an AI task that would normally be opaque."
2. "Here is the Harnessfile."
3. "Here is the dry-run plan."
4. "Here is a policy blocking a risky action."
5. "Here is the approved run."
6. "Here is the ledger."
7. "Here is the eval that prevents the mistake next time."

That story is the product.

## Open-Source Community Plan

The project needs community infrastructure before it gets attention:

- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- issue templates
- pull request template
- security policy
- public roadmap
- good-first issues
- adapter request issues
- eval request issues
- playbook request issues

It also needs release infrastructure:

- `pyproject.toml`
- `delegation_bot` package namespace
- `CHANGELOG.md`
- release checklist
- clear license strategy
- documented business model assumptions
- TestPyPI smoke release before PyPI
- domain strategy before launch traffic

The contributor ladder should be:

1. fix docs
2. add an eval
3. add a playbook
4. add an adapter
5. improve policy engine
6. help govern schema evolution

## Content Plan

Write public artifacts that teach the category:

- "Why agents need dry-runs"
- "A Harnessfile for AI work"
- "Run ledgers are the missing primitive for agent trust"
- "Policy before autonomy"
- "Why agents need promotion paths, not just guardrails"
- "How to compare OpenAI Agents SDK, LangGraph, GitHub Actions, and MCP runs"
- "How to compare Claude Code, Codex, and OpenAI agent runs"
- "How to turn agent failures into evals"

Each post should point back to a runnable example.

## Quality Bar

The project should feel serious from day one:

- green QA command
- stable examples
- explicit roadmap
- typed public functions
- changelog before first release
- no hidden live writes
- backups before major changes
- decision log for architectural changes

## Anti-Goals

- Do not become another generic agent framework.
- Do not make safety feel like suppression.
- Do not hide policy decisions behind prompts.
- Do not run live writes without dry-run and approval paths.
- Do not optimize for fake popularity.
- Do not add adapters before the adapter contract is testable.
- Do not let demos outrun trust.

## Metrics

Stars are a lagging indicator. Track leading indicators:

- time to first successful dry-run
- number of valid Harnessfiles in the wild
- number of community playbooks
- number of adapter contributors
- number of failures converted into evals
- repeat contributors
- issue response time
- release cadence

## First Public Release Definition

Version `0.1.0` should ship when:

- `delegation validate` exists
- `delegation plan` exists
- dry-run ledger exists
- GitHub Issue adapter can be planned
- adapter contracts are visible from the CLI
- at least 10 eval tests exist
- README has a 60-second demo
- community files exist
- GitHub Action runs QA
- package metadata and license metadata are correct

The project should be tiny but unmistakable.
