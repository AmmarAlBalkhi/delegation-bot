# Evidence Tools

DelegationHQ should treat proof capture as a tool layer, not as one recorder.

RunPrint is the first recorder/evidence agent in the ecosystem. It should stay
important, but DelegationHQ must also accept proof from tests, browser/session
recorders, CRM audit logs, API traces, workflow monitors, local scripts,
research artifact trackers, and future business-workflow tools.

Simple version:

```text
Agent asks to act.
DelegationHQ checks the passport and gate.
Human approves risky work.
Evidence tool records what happened.
Ledger keeps the proof.
Evals judge the result.
```

## Evidence Tool Contract

A compatible evidence tool should be able to provide:

- `action_id`: the Agent Gate action this proof belongs to
- `evidence_tool`: stable tool id, such as `runprint`, `test-reporter`, or
  `crm-audit`
- `tool_kind`: recorder, test, browser, crm, api, monitor, workflow, or another
  clear category
- `recording_id`: stable id for this recording/session
- `evidence_bundle_id`: stable id for the proof bundle
- `artifact_manifest`: files, URLs, logs, reports, screenshots, traces, or
  summaries that prove what happened
- `summary`: plain language result
- `source`: local path, URL, or note identifying where the evidence came from

The generic lane is:

```bash
delegation evidence-ingest --ledger .delegation/agent-run.jsonl --action-id ACTION_ID --tool TOOL --tool-kind KIND --recording-id REC --bundle-id BUNDLE --artifact id:kind:path
```

The RunPrint-specific compatibility lane remains:

```bash
delegation runprint-ingest --ledger .delegation/agent-run.jsonl --action-id ACTION_ID --recording-id REC --bundle-id BUNDLE --artifact id:kind:path
```

The local app can append the same generic evidence receipt when served with:

```bash
delegation app-serve --workspace . --allow-actions
```

That app write still requires `LOCAL_APP_WRITE`. It does not execute agents.

## Product Rule

The Evidence area should stay broad:

```text
Evidence = proof from any compatible recorder or system.
RunPrint = one evidence tool inside the ecosystem.
```

This keeps DelegationHQ bigger than a recorder dashboard and ready for hosted,
team, and business-workflow surfaces later.
