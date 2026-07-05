# Contributor License Policy

Delegation Bot uses Apache-2.0. Contributions intentionally submitted to the
project should be contributed under the same license unless the project states
otherwise.

This is not legal advice. It is the project operating policy so contributors
and maintainers know what to expect.

## Current Policy

Current lightweight policy:

- inbound contributions are accepted under Apache-2.0
- contributors should only submit work they have the right to contribute
- contributors should avoid copying incompatible code, prompts, datasets, or
  generated output from restricted sources
- maintainers may ask for a sign-off if provenance is unclear
- no separate Contributor License Agreement is required right now

## DCO Option

The Developer Certificate of Origin is a lightweight sign-off workflow. The
official DCO text is maintained at:

```text
https://developercertificate.org/
```

If the project adopts DCO enforcement later, contributors would sign commits:

```bash
git commit -s -m "Describe the change"
```

That adds a line like:

```text
Signed-off-by: Name <email@example.com>
```

## Recommendation

Recommended posture before broad public launch:

1. Keep the current Apache-2.0 inbound=outbound policy documented.
2. Encourage DCO sign-offs for outside contributors.
3. Require DCO sign-offs once external contribution volume grows.
4. Avoid a CLA unless a future governance, relicensing, or enterprise
   requirement makes it worth the extra friction.

Simple version:

```text
No surprise legal trap.
No heavy CLA yet.
Use Apache-2.0.
Use DCO when community grows.
```

## Why Not Require A CLA Now

A CLA can make sense for some projects, especially when rights management,
corporate contribution workflows, or future relicensing are central concerns.

For Delegation Bot right now, the bigger risk is making early contribution feel
too heavy. A DCO-style sign-off is easier to explain and fits the low-friction
open-source path better.

## Maintainer Checklist

Before accepting significant outside contributions:

- confirm the contribution is compatible with Apache-2.0
- confirm generated or AI-assisted code is reviewable and test-covered
- confirm no secrets, private data, or restricted third-party content were
  introduced
- ask for a DCO sign-off when provenance is unclear
- run `python scripts/qa.py`
