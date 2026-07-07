# RunPrint Recorder Boundary

RunPrint is the recorder/evidence agent in the DelegationHQ ecosystem.

Simple version:

```text
DelegationHQ controls the mission.
Agents do the work.
RunPrint records the proof.
Evals judge the proof.
```

## Why It Exists

DelegationHQ should not trust an agent just because the agent says a task is
done. A mission needs proof: ledgers, diffs, screenshots, check links, reports,
approvals, and other artifacts that can be reviewed later.

The `runprint.recorder` adapter is the dry-run contract for that proof capture.
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
