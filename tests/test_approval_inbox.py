from __future__ import annotations

import unittest
from pathlib import Path

from delegation_bot.agent_gate import build_agent_gate_audit_report, build_agent_gate_events, build_agent_gate_report
from delegation_bot.approval_inbox import (
    build_approval_decision_events,
    build_approval_decision_receipt,
    build_approval_inbox_report,
    render_approval_decision_receipt,
    render_approval_inbox_report,
)
from delegation_bot.harness_manifest import load_manifest
from delegation_bot.harness_plan import build_dry_run_ledger, compile_plan


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "ai-harness-control-plane.yaml"


class ApprovalInboxTests(unittest.TestCase):
    def test_pending_gate_receipt_becomes_approval_card(self) -> None:
        ledger = _pending_gate_ledger()

        report = build_approval_inbox_report(ledger, ledger_source="ledger.jsonl")
        text = render_approval_inbox_report(report)

        self.assertEqual(report.status, "needs_attention")
        self.assertEqual(report.pending_count, 1)
        self.assertEqual(report.items[0].status, "pending_approval")
        self.assertEqual(report.items[0].available_decisions, ("approve", "block"))
        self.assertIn("Approval Inbox", text)
        self.assertIn("pending_approval", text)

    def test_approval_decision_updates_inbox_and_agent_audit(self) -> None:
        ledger = _pending_gate_ledger()
        action_id = ledger[-1]["action_id"]
        decision_events = build_approval_decision_events(
            ledger,
            action_id=action_id,
            decision="approve",
            approver="Ammar",
            reason="Looks scoped and recorder evidence is planned.",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        ledger.extend(event.to_dict() for event in decision_events)

        inbox = build_approval_inbox_report(ledger, ledger_source="ledger.jsonl")
        audit = build_agent_gate_audit_report(ledger, ledger_source="ledger.jsonl")
        receipt = build_approval_decision_receipt(decision_events[0], ledger_source="ledger.jsonl")
        receipt_text = render_approval_decision_receipt(receipt)

        self.assertEqual(inbox.status, "ready")
        self.assertEqual(inbox.approved_count, 1)
        self.assertEqual(inbox.items[0].status, "approved")
        self.assertEqual(inbox.items[0].latest_decision.approver, "Ammar")
        self.assertEqual(audit.status, "ready_for_recording")
        self.assertEqual(audit.items[0].outcome, "recording_planned")
        self.assertEqual(receipt.event_type, "approval.granted")
        self.assertIn("Approval Decision", receipt_text)

    def test_human_block_stops_inbox_and_agent_audit(self) -> None:
        ledger = _pending_gate_ledger()
        action_id = ledger[-1]["action_id"]
        ledger.extend(
            event.to_dict()
            for event in build_approval_decision_events(
                ledger,
                action_id=action_id,
                decision="block",
                approver="Ammar",
                reason="Too broad.",
            )
        )

        inbox = build_approval_inbox_report(ledger, ledger_source="ledger.jsonl")
        audit = build_agent_gate_audit_report(ledger, ledger_source="ledger.jsonl")

        self.assertEqual(inbox.status, "blocked")
        self.assertEqual(inbox.blocked_count, 1)
        self.assertEqual(inbox.items[0].status, "blocked_by_human")
        self.assertEqual(audit.status, "blocked")
        self.assertEqual(audit.items[0].outcome, "blocked_by_human")

    def test_decision_requires_matching_gate_receipt(self) -> None:
        with self.assertRaisesRegex(ValueError, "No Agent Gate receipt"):
            build_approval_decision_events(
                [],
                action_id="agent_gate.missing.action",
                decision="approve",
                approver="Ammar",
            )


def _pending_gate_ledger() -> list[dict[str, object]]:
    manifest = load_manifest(EXAMPLE)
    plan = compile_plan(manifest, source=str(EXAMPLE))
    ledger = [event.to_dict() for event in build_dry_run_ledger(plan, run_id="run-1")]
    gate = build_agent_gate_report(
        manifest=manifest,
        manifest_source=str(EXAMPLE),
        agent_id="implementer",
        action="create_pull_request",
        target="repository",
    )
    ledger.extend(event.to_dict() for event in build_agent_gate_events(gate, run_id="run-1", start_sequence=len(ledger) + 1))
    return ledger


if __name__ == "__main__":
    unittest.main()
