# OpenTelemetry Mapping

This document maps DelegationHQ run ledgers to OpenTelemetry concepts.

Simple version: the JSONL ledger stays the product-native source of truth.
OpenTelemetry becomes an export shape for teams that want traces, logs,
dashboards, alerts, and long-term observability.

## Current Reference Points

OpenTelemetry semantic conventions define common names and meanings for
telemetry data. The current docs include areas for CI/CD, traces, logs, events,
MCP, OpenAI, and Generative AI. The OpenTelemetry docs also note that GenAI
semantic conventions moved to their own repository, so exporter code should
read those conventions directly when we implement it.

## Mapping Rule

One DelegationHQ run should map to one trace.

```text
run_id -> trace
LedgerEvent -> span event or log record
PlanAction -> span
adapter result -> child span plus span events
eval result -> span event and log record
promotion decision -> span event and log record
```

The ledger keeps every event in order. OpenTelemetry makes those events easier
to search, correlate, and alert on in external systems.

## Resource Attributes

Every exported item should include:

```text
service.name = delegationhq
service.version = <package version>
deployment.environment = local | ci | hosted
delegation.harness.id = <Harnessfile id>
delegation.run.id = <ledger run_id>
delegation.ledger.schema = ledger.v1
```

## Span Shape

Root span:

```text
name = delegation.run
kind = internal
attributes:
  delegation.harness.id
  delegation.run.id
  delegation.mode
  delegation.objective
```

Action spans:

```text
name = delegation.action
kind = internal
attributes:
  delegation.action.id
  delegation.action.type
  delegation.action.risk
  delegation.action.requires_approval
```

Adapter spans:

```text
name = delegation.adapter
kind = internal
attributes:
  delegation.adapter.id
  delegation.adapter.kind
  delegation.adapter.risk
  delegation.adapter.status
  delegation.dry_run
```

## Event Mapping

Recommended event names:

```text
plan.compiled -> delegation.plan.compiled
dry_run.* -> delegation.dry_run.event
adapter.* -> delegation.adapter.event
eval.result -> delegation.eval.result
promotion.* -> delegation.promotion.event
github.issue.planned -> delegation.github.issue.planned
```

Keep the original ledger event type as:

```text
delegation.ledger.event_type
```

That lets us preserve DelegationHQ semantics while still following
OpenTelemetry naming discipline.

## Logs

Every `LedgerEvent` can also be exported as a structured log record.

Recommended log fields:

```text
timestamp = LedgerEvent.timestamp
body = LedgerEvent.message
severity = INFO | WARN | ERROR
attributes:
  delegation.run.id
  delegation.sequence
  delegation.event.type
  delegation.event.status
  delegation.action.id
```

Status mapping:

```text
planned -> INFO
running -> INFO
succeeded -> INFO
passed -> INFO
blocked -> WARN
skipped -> WARN
failed -> ERROR
```

## GenAI And Tool Attributes

When an adapter touches model or tool concepts, an exporter should prefer the
official OpenTelemetry GenAI, MCP, OpenAI, CI/CD, and trace semantic
conventions available at implementation time.

Delegation-specific attributes should use the `delegation.*` prefix and should
not pretend to be official OpenTelemetry semantic attributes.

Examples:

```text
delegation.model.provider = openai | anthropic | local
delegation.model.name = <declared model>
delegation.tool.name = <MCP or local tool name>
delegation.approval.required = true | false
delegation.eval.id = <eval id>
delegation.feedback.marker = <dedupe marker>
```

## First Exporter Slice

Do not start with a collector integration.

Start with a deterministic local command. This first slice now exists:

```bash
delegation otel .delegation/latest.jsonl --output .delegation/latest-otel.json
```

That command should:

- read a JSONL ledger
- validate event ordering
- convert events into trace-like JSON
- preserve original ledger event details
- redact secrets using the same sanitizer as feedback issues
- avoid network calls

Tiny version:

```text
Ledger stays truth.
OTel export makes truth easier to search later.
No upload by default.
```

After that local shape is stable, add an OTLP exporter behind explicit config.

## Non-Goals For Now

- no live telemetry upload by default
- no vendor-specific dashboard assumptions
- no loss of original ledger details
- no raw prompts or secrets in exported attributes

OpenTelemetry should make the evidence easier to operate. It should not weaken
the ledger, privacy, or approval model.
