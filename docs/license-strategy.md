# License Strategy

DelegationHQ uses the Apache License 2.0.

This document is not legal advice. It records the product and engineering
reasoning behind the license choice before the project grows a larger external
contributor base.

## Decision

Chosen license:

```text
Apache-2.0
```

Decision date:

```text
2026-07-04
```

Package metadata:

```text
license = "Apache-2.0"
license-files = ["LICENSE", "NOTICE"]
```

Simple meaning: DelegationHQ stays permissive and easy to adopt, but gets a
clearer patent story, clearer contribution treatment, and an attribution notice.

## Why This Fits

DelegationHQ is becoming infrastructure for agentic AI. Serious users may
care about:

- patent grants
- contribution terms
- commercial adoption comfort
- compatibility with company policies
- whether cloud vendors can wrap the tool without contributing back
- whether the project name and attribution stay visible

Apache-2.0 is a good default for that shape. It keeps adoption broad like MIT,
but gives infrastructure users more explicit legal machinery.

## Options Considered

### MIT

Best when the only goal is maximum adoption with the least friction.

Tradeoff: MIT is short and familiar, but it does not include the explicit patent
grant that many infrastructure users prefer.

### Apache-2.0

Best when the goal is permissive adoption plus clearer patent and contribution
terms.

Tradeoff: Apache-2.0 is longer and asks modified files to state changes, but it
is still business-friendly and widely used for infrastructure.

### GPLv3 Or AGPLv3

Best when the goal is strong source-sharing requirements.

Tradeoff: this can protect openness, but it can also reduce adoption inside
companies and make plugin, adapter, and hosted-service ecosystems more
complicated.

## Business Position

Apache-2.0 supports the open-core direction:

- the local CLI, Harnessfile planner, ledger, evals, and adapter contracts stay
  open
- paid offerings can still exist around hosting, dashboards, team approvals,
  private adapters, support, SSO, audit exports, and retention controls
- contributors and companies can adopt the tool without a copyleft obligation

The money plan stays in `docs/business-model.md` so it does not distract from
the core engineering loop.

## Current Obligations

Keep these files aligned:

- `LICENSE` contains Apache License 2.0
- `NOTICE` identifies DelegationHQ and the copyright holder
- `pyproject.toml` declares `Apache-2.0`
- README and release docs say Apache-2.0
- contributor docs say submitted contributions use Apache-2.0 unless explicitly
  stated otherwise

## Future Legal Work

Before a larger public contribution push, decide whether to add:

- Developer Certificate of Origin signoff
- contributor license agreement
- trademark and brand usage policy
- paid hosted terms of service
- privacy policy for any hosted dashboard

The current decision is enough for the open-source repository, but those future
items matter if DelegationHQ becomes a hosted product or company.
