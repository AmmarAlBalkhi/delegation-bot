# RunPrint Recorder Boundary

RunPrint is the current recorder/evidence tool in the DelegationHQ ecosystem.
It is important, but it is not the whole product.

Simple version:

```text
DelegationHQ controls the mission.
Agents do the work.
Evidence tools record the proof.
Evals judge the proof.
```

## Why It Exists

DelegationHQ should not trust an agent just because the agent says a task is
done. A mission needs proof: ledgers, diffs, screenshots, check links, reports,
approvals, and other artifacts that can be reviewed later.

The `runprint.recorder` adapter is the first dry-run contract for that proof capture.
It lets a Harnessfile say what evidence should be recorded before any recorder
runs live.

## Current Adapter

`runprint.recorder` is dry-run only today. It does not read files, capture
screenshots, call a service, or write a real evidence bundle.

It plans:

- `recording_session`: the planned recording scope and workspace
- `evidence_bundle`: the planned proof bundle and artifact manifest
- `run_ledger`: the DelegationHQ ledger events for later evals

Required evidence:

- `recording_id`
- `evidence_bundle_id`
- `artifact_manifest`

Inspect planned evidence bundles:

```bash
delegation evidence --ledger .delegation/demo.jsonl
```

This report is intentionally read-only. It summarizes the recorder plan already
written to the ledger.

Compare an Agent Gate receipt with RunPrint evidence:

```bash
delegation agent-gate examples/ai-harness-control-plane.yaml implementer \
  --action create_pull_request \
  --target repository \
  --approval pull_request \
  --ledger .delegation/demo.jsonl \
  --write
delegation agent-audit --ledger .delegation/demo.jsonl
```

Today that usually means "gate approved, evidence bundle planned." Later live
recorder events will let the same audit say what actually happened.

## Ingest Recorded Evidence

When RunPrint or another recorder has produced a proof bundle, append it to the
DelegationHQ ledger:

```bash
delegation runprint-ingest \
  --ledger .delegation/demo.jsonl \
  --action-id agent_gate.implementer.create_pull_request \
  --recording-id rec-demo \
  --bundle-id bundle-demo \
  --artifact run-ledger:jsonl:.delegation/demo.jsonl \
  --summary "Recorded ledger and approval evidence."
```

Then verify:

```bash
delegation agent-audit --ledger .delegation/demo.jsonl
delegation approval-inbox --ledger .delegation/demo.jsonl
```

Simple version:

```text
Agent Gate receipt = what was allowed.
Approval receipt = who said yes/no.
RunPrint ingest = what was recorded.
Agent audit = compare them.
```

That line says RunPrint because `runprint-ingest` is the first implemented
recorder lane. Future recorder, monitor, test, browser, CRM, API, or workflow
evidence tools should fit the same DelegationHQ proof model.

`runprint-ingest` can also read a JSON bundle:

```bash
delegation runprint-ingest --ledger .delegation/demo.jsonl --bundle runprint-bundle.json
```

The bundle should include `action_id`, `recording_id`, `evidence_bundle_id`,
and `artifacts` or `artifact_manifest`.

## Harnessfile Example

```yaml
executors:
  - id: evidence_recorder
    kind: recorder
    adapter: runprint.recorder
    purpose: Plan the RunPrint evidence bundle before proof capture.
    inputs:
      workspace: AmmarAlBalkhi/delegation-bot
      scope: Record dry-run ledger, evals, workflow preview, and approval evidence.
      artifacts:
        - id: run-ledger
          kind: jsonl
          path: .delegation/demo.jsonl
        - id: eval-report
          kind: report
          path: .delegation/evals.json
```

## Trust Boundary

The recorder does not approve work.

The recorder creates proof. DelegationHQ gates, ledgers, and evals decide whether
that proof is enough for promotion or live action.

## Future Live Path

A live recorder integration should stay preview-first:

1. Plan the artifact manifest.
2. Require approval when the capture scope is sensitive.
3. Capture only the declared artifacts.
4. Write bundle IDs and artifact links back to the ledger.
5. Let evals pass, block, or create feedback from the recorded evidence.
