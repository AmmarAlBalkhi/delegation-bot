# Business Model

This document keeps the money plan in one place so it does not distract from
the core product.

## Honest Starting Point

People will not pay much for "a bot that creates GitHub Issues."

People may pay for:

```text
Mission control for AI agents at work.
```

That means planning, approvals, run history, cost control, evals, audit trails,
team workflows, and integrations across agent harnesses.

## Who Might Pay

Likely buyers:

- AI startups running agent workflows in production
- engineering managers responsible for agent-written code
- platform teams building internal AI automation
- regulated teams that need approval evidence and audit logs
- consultancies managing AI automation for clients

They pay when the tool reduces risk, saves engineering time, or gives leadership
visibility into what AI systems are doing.

## Free Core

The open-source core should stay useful by itself:

- Harnessfile validation
- dry-run planning
- local run ledger
- basic evals
- adapter contracts
- package CLI
- basic GitHub-native task workflow

This is the trust engine and adoption loop.

The repository uses Apache-2.0 so the free core can stay permissive while still
having clearer patent, contribution, and attribution terms.

## Paid Surface

Possible paid layers:

- hosted dashboard
- searchable run ledger history
- team approval workflows
- GitHub App installation flow
- Slack, Linear, Jira, and enterprise adapters
- SSO, RBAC, audit logs, and retention controls
- compliance exports
- managed eval monitoring
- private adapter development
- onboarding and support

## First Revenue Path

The likely first money is not a SaaS subscription.

The likely order is:

1. consulting and setup for teams trying agentic workflows
2. paid private adapters or playbooks
3. hosted dashboard for teams already using the CLI
4. enterprise controls after real team usage exists

## Pricing Hypothesis

Do not price before usage is proven.

Early hypothesis:

- open source: free
- solo hosted: low monthly price
- team hosted: per-seat or per-workspace
- enterprise: custom, based on SSO, audit, retention, support, and deployment

The important thing is not the exact price. The important thing is proving that
teams care about control, evidence, and repeatability for agent work.

## What Not To Do

- Do not hide the useful core behind a paywall.
- Do not sell safety theater.
- Do not chase enterprise features before the CLI is loved.
- Do not let monetization distract from the Harnessfile, ledger, evals, and
  adapters.
- Do not promise hosted plans until there is a real hosted product.

## Business Proof Points To Watch

Track:

- repeat CLI usage
- teams with more than one Harnessfile
- failures converted into evals
- adapter requests from real users
- requests for history/search/dashboard
- requests for SSO, RBAC, retention, or audit export
- users asking for help installing it at work

Those signals matter more than stars for the business.
