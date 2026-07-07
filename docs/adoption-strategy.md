# Adoption Strategy

This is an adoption map, not a traction claim.

DelegationHQ should grow because developers can understand it quickly, run it
safely, and extend it without asking for permission.

## Category

DelegationHQ should own a clear category:

```text
AI delegation control plane
```

Plain-language version:

```text
Mission control for agentic work.
```

It should sit above execution harnesses such as Codex, Claude Code, Anthropic
Claude, OpenAI Agents SDK, LangGraph, GitHub Actions, MCP tools, and local
scripts.

## Audience

Primary users are AI builders who already have agents or automations and now
need control:

- solo builders shipping AI tools
- open-source maintainers using coding agents
- engineering teams making agent work auditable
- platform engineers building internal AI automation
- researchers comparing agent harnesses

## Product Promise

```text
Plan it once. Dry-run it. Approve it. Execute anywhere. Learn from every run.
```

And:

```text
Give agents more power as they prove themselves.
```

## Launch Narrative

The first public story should show one loop:

1. A user describes an AI mission.
2. DelegationHQ creates or validates a Harnessfile.
3. The Harnessfile compiles into a dry-run plan.
4. Policy gates block or request approval for risky actions.
5. The run writes evidence to a ledger.
6. Evals catch failures and turn them into improvements.
7. Agents earn more autonomy only when evidence supports it.

That story is the product.

## Growth Loops

Developer loop:

1. Run `delegation demo`.
2. Create a Harnessfile with `delegation init`.
3. Inspect the dry-run ledger.
4. Add one playbook, eval, or adapter.
5. Share the workflow because it feels useful and safe.

Trust loop:

1. A run fails.
2. The failure becomes a ledger event.
3. The event becomes an eval or improvement issue.
4. The eval prevents regression.
5. The system earns more trust through use.

## Quality Bar

The project should feel serious from day one:

- green QA command
- stable examples
- no live writes by default
- clear install path
- clear release checklist
- typed public functions where they matter
- changelog before first release
- backups before major changes
- decision log for architectural changes

## Anti-Goals

- Do not become another generic agent framework.
- Do not make safety feel like suppression.
- Do not hide policy decisions behind prompts.
- Do not run live writes without dry-run and approval paths.
- Do not optimize for fake popularity.
- Do not let demos outrun trust.

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
