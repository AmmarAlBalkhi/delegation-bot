from __future__ import annotations

import unittest
from pathlib import Path

from delegation_bot.agent_gate import build_agent_gate_audit_report, build_agent_gate_events, build_agent_gate_report
from delegation_bot.approval_inbox import build_approval_inbox_report
from delegation_bot.harness_manifest import load_manifest
from delegation_bot.harness_plan import build_dry_run_ledger, compile_plan
from delegation_bot.runprint_ingest import (
    RunPrintArtifact,
    artifacts_from_values,
    build_runprint_ingest_receipt,
    build_runprint_recording_events,
    render_runprint_ingest_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "ai-harness-control-plane.yaml"


class RunPrintIngestTests(unittest.TestCase):
    def test_runprint_ingest_event_records_matching_gate_action(self) -> None:
        ledger = _gate_ledger()
        action_id = ledger[-1]["action_id"]

        events = build_runprint_recording_events(
            ledger,
            action_id=action_id,
            recording_id="rec-1",
            evidence_bundle_id="bundle-1",
            artifacts=(RunPrintArtifact(id="run-ledger", kind="jsonl", path=".delegation/demo.jsonl"),),
            summary="Recorded ledger and approval evidence.",
            source="runprint://local/rec-1",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        ledger.extend(event.to_dict() for event in events)
        audit = build_agent_gate_audit_report(ledger, ledger_source="ledger.jsonl")
        inbox = build_approval_inbox_report(ledger, ledger_source="ledger.jsonl")
        receipt = build_runprint_ingest_receipt(events[0], ledger_source="ledger.jsonl")
        receipt_text = render_runprint_ingest_receipt(receipt)

        self.assertEqual(events[0].type, "runprint.recording.completed")
        self.assertEqual(events[0].action_id, action_id)
        self.assertEqual(events[0].details["target_action_id"], action_id)
        self.assertEqual(audit.status, "recorded")
        self.assertEqual(audit.items[0].evidence_status, "recorded")
        self.assertEqual(inbox.items[0].status, "recorded")
        self.assertIn("RunPrint Recording Ingest", receipt_text)

    def test_runprint_ingest_can_use_bundle_shape(self) -> None:
        ledger = _gate_ledger()
        action_id = ledger[-1]["action_id"]

        events = build_runprint_recording_events(
            ledger,
            bundle={
                "action_id": action_id,
                "recording_id": "rec-bundle",
                "evidence_bundle_id": "bundle-json",
                "summary": "Recorded from bundle file.",
                "source": "bundle.json",
                "artifacts": [
                    {"id": "diff", "kind": "patch", "path": "artifacts/diff.patch"},
                    {"id": "logs", "kind": "text", "path": "artifacts/log.txt"},
                ],
            },
        )

        self.assertEqual(events[0].details["recording_id"], "rec-bundle")
        self.assertEqual(events[0].details["evidence_bundle_id"], "bundle-json")
        self.assertEqual(events[0].details["artifact_count"], 2)

    def test_artifact_values_accept_simple_and_structured_forms(self) -> None:
        artifacts = artifacts_from_values(("artifacts/log.txt", "diff:patch:artifacts/diff.patch"))

        self.assertEqual(artifacts[0].id, "log.txt")
        self.assertEqual(artifacts[0].kind, "artifact")
        self.assertEqual(artifacts[1].id, "diff")
        self.assertEqual(artifacts[1].kind, "patch")

    def test_recording_for_other_action_does_not_record_gate_item(self) -> None:
        ledger = _gate_ledger()
        ledger.append(
            {
                "run_id": "run-1",
                "sequence": len(ledger) + 1,
                "timestamp": "2026-01-01T00:00:00+00:00",
                "type": "runprint.recording.completed",
                "status": "completed",
                "message": "Unrelated recording.",
                "action_id": "agent_gate.other.action",
                "details": {"target_action_id": "agent_gate.other.action"},
            }
        )

        audit = build_agent_gate_audit_report(ledger, ledger_source="ledger.jsonl")

        self.assertEqual(audit.status, "ready_for_recording")
        self.assertEqual(audit.items[0].evidence_status, "planned")
        self.assertEqual(audit.recorded_event_count, 1)

    def test_runprint_ingest_requires_matching_gate_receipt(self) -> None:
        with self.assertRaisesRegex(ValueError, "No Agent Gate receipt"):
            build_runprint_recording_events(
                [],
                action_id="agent_gate.missing.action",
                recording_id="rec-1",
                evidence_bundle_id="bundle-1",
                artifacts=(RunPrintArtifact(id="proof", kind="text", path="proof.txt"),),
            )


def _gate_ledger() -> list[dict[str, object]]:
    manifest = load_manifest(EXAMPLE)
    plan = compile_plan(manifest, source=str(EXAMPLE))
    ledger = [event.to_dict() for event in build_dry_run_ledger(plan, run_id="run-1")]
    gate = build_agent_gate_report(
        manifest=manifest,
        manifest_source=str(EXAMPLE),
        agent_id="implementer",
        action="create_pull_request",
        target="repository",
        provided_approvals=("pull_request",),
    )
    ledger.extend(event.to_dict() for event in build_agent_gate_events(gate, run_id="run-1", start_sequence=len(ledger) + 1))
    return ledger


if __name__ == "__main__":
    unittest.main()
