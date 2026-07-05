# Local Classifier Policy Profiles

The `local.classifier` adapter gives Delegation Bot a lightweight local risk
review step without letting a model approve itself.

Simple version:

```text
Profile sets the rules.
Classifier matches the plan against those rules.
Recommended gate is written as evidence.
Human approval still handles risky action.
```

## Current Profiles

- `delegation.default`: general AI delegation risk checks.
- `release-readiness`: stricter checks for package, tag, release, and publish
  work.
- `code-review`: checks for security, permission, credential, and dependency
  risk language.

Profiles are deterministic term sets today. They are intentionally simple so
users can understand why a plan was marked low, medium, high, or blocked.

## Evidence

A planned `local.classifier` result now includes:

- `classification`: `low`, `medium`, `high`, or `blocked`
- `policy_profile`: the deterministic profile id
- `recommended_gate`: `none`, `review_recommended`, `approval_required`, or
  `fix_missing_inputs`
- `matched_terms`: which profile terms matched the plan or policy text
- `reasons`: short plain-English reasons

## Example

```yaml
executors:
  - id: release_risk_classifier
    kind: ml_model
    adapter: local.classifier
    inputs:
      profile: release-readiness
      plan: Verify package metadata, changelog, tests, and artifacts before release.
      policy: Require approvals for release publication and workflow changes.
```

## Trust Boundary

This feature is deliberately hybrid:

- Local or hosted AI may draft plans.
- The classifier profile writes structured risk evidence.
- Approval gates and evals remain deterministic.
- Humans still approve risky live actions.

Future local models can add richer explanations, but they should not become the
authority that grants their own autonomy.
