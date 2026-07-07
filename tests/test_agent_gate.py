from __future__ import annotations

import unittest
from pathlib import Path

from delegation_bot.agent_gate import (
    build_agent_gate_audit_report,
    build_agent_gate_events,
    build_agent_gate_report,
    render_agent_gate_audit_report,
    render_agent_gate_report,
)
from delegation_bot.harness_manifest import load_manifest
from delegation_bot.harness_plan import build_dry_run_ledger, compile_plan


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "ai-harness-control-plane.yaml"
REGISTRY = ROOT / "examples" / "agent-passports.yaml"


class AgentGateTests(unittest.TestCase):
    def test_pr_creation_requires_approval_for_implementer(self) -> None:
        manifest = load_manifest(EXAMPLE)

        report = build_agent_gate_report(
            manifest=manifest,
            manifest_source=str(EXAMPLE),
            agent_id="implementer",
            action="create_pull_request",
            target="repository",
        )
        text = render_agent_gate_report(report)

        self.assertEqual(report.decision, "approval_required")
        self.assertFalse(report.blocked)
        self.assertIn("pull_request", report.matched_approvals)
        self.assertTrue(any("write.pull_request_draft" in check.message for check in report.checks))
        self.assertIn("Decision: approval_required", text)

    def test_provided_approval_allows_implementer_pr_preview(self) -> None:
        manifest = load_manifest(EXAMPLE)

        report = build_agent_gate_report(
            manifest=manifest,
            manifest_source=str(EXAMPLE),
            agent_id="implementer",
            action="create_pull_request",
            target="repository",
            provided_approvals=("pull_request",),
        )

        self.assertEqual(report.decision, "allow")
        self.assertEqual(report.status, "ready")

    def test_approval_is_not_permission_for_wrong_agent(self) -> None:
        manifest = load_manifest(EXAMPLE)

        report = build_agent_gate_report(
            manifest=manifest,
            manifest_source=str(EXAMPLE),
            agent_id="planner",
            action="create_pull_request",
            target="repository",
            provided_approvals=("pull_request",),
        )

        self.assertEqual(report.decision, "block")
        self.assertTrue(report.blocked)
        self.assertTrue(any(check.id == "scope.action" and check.status == "blocked" for check in report.checks))

    def test_unknown_agent_blocks(self) -> None:
        report = build_agent_gate_report(
            registry_paths=(REGISTRY,),
            agent_id="missing_agent",
            action="read.run_ledger",
            target="run_ledger",
        )

        self.assertEqual(report.decision, "block")
        self.assertIn("Register the agent", report.next_action)

    def test_custom_crm_write_requires_approval(self) -> None:
        report = build_agent_gate_report(
            registry_paths=(REGISTRY,),
            agent_id="crm_update_agent",
            action="crm.write",
            target="crm.accounts",
        )

        self.assertEqual(report.decision, "approval_required")
        self.assertEqual(report.matched_approvals, ("crm.write",))
        self.assertIn("human_confirmation", report.required_evidence)

    def test_custom_read_only_agent_can_be_allowed(self) -> None:
        report = build_agent_gate_report(
            registry_paths=(REGISTRY,),
            agent_id="repo_cli_agent",
            action="read.run_ledger",
            target="run_ledger",
        )

        self.assertEqual(report.decision, "allow")
        self.assertEqual(report.effective_risk, "low")

    def test_out_of_scope_target_blocks(self) -> None:
        report = build_agent_gate_report(
            registry_paths=(REGISTRY,),
            agent_id="repo_cli_agent",
            action="read.run_ledger",
            target="crm.accounts",
        )

        self.assertEqual(report.decision, "block")
        self.assertTrue(any(check.id == "scope.target" and check.status == "blocked" for check in report.checks))

    def test_critical_agent_without_approval_policy_blocks(self) -> None:
        report = build_agent_gate_report(
            registry_paths=(ROOT / "tests" / "fixtures" / "high-risk-agent-passports.yaml",),
            agent_id="deploy_agent",
            action="deploy.production",
            target="production",
        )

        self.assertEqual(report.decision, "block")
        self.assertEqual(report.effective_risk, "critical")
        self.assertIn("Declare required approvals", report.next_action)

    def test_agent_gate_report_becomes_ledger_event(self) -> None:
        manifest = load_manifest(EXAMPLE)
        report = build_agent_gate_report(
            manifest=manifest,
            manifest_source=str(EXAMPLE),
            agent_id="implementer",
            action="create_pull_request",
            target="repository",
            provided_approvals=("pull_request",),
        )

        events = build_agent_gate_events(report, run_id="run-1", start_sequence=8, timestamp="2026-01-01T00:00:00+00:00")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].sequence, 8)
        self.assertEqual(events[0].type, "agent.gate.previewed")
        self.assertEqual(events[0].status, "allow")
        self.assertEqual(events[0].action_id, "agent_gate.implementer.create_pull_request")
        self.assertEqual(events[0].details["agent_gate"]["decision"], "allow")

    def test_audit_reports_missing_gate_receipts(self) -> None:
        report = build_agent_gate_audit_report([], ledger_source="empty.jsonl")
        text = render_agent_gate_audit_report(report)

        self.assertEqual(report.status, "missing_gate")
        self.assertTrue(report.blocked)
        self.assertIn("No Agent Gate preview events", text)

    def test_audit_reports_ready_for_recording_when_runprint_bundle_exists(self) -> None:
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

        report = build_agent_gate_audit_report(ledger, ledger_source="ledger.jsonl")

        self.assertEqual(report.status, "ready_for_recording")
        self.assertFalse(report.blocked)
        self.assertEqual(report.runprint_bundle_count, 1)
        self.assertEqual(report.items[0].outcome, "recording_planned")

    def test_audit_reports_recorded_when_runprint_recording_events_exist(self) -> None:
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
        ledger.append(
            {
                "run_id": "run-1",
                "sequence": len(ledger) + 1,
                "timestamp": "2026-01-01T00:00:00+00:00",
                "type": "runprint.recording.completed",
                "status": "completed",
                "message": "RunPrint recorded execution evidence.",
                "action_id": "evidence_recorder",
                "details": {"recording_id": "recording-1"},
            }
        )

        report = build_agent_gate_audit_report(ledger, ledger_source="ledger.jsonl")

        self.assertEqual(report.status, "recorded")
        self.assertEqual(report.recorded_event_count, 1)
        self.assertEqual(report.items[0].outcome, "recorded")

    def test_audit_blocks_allowed_gate_without_runprint_evidence(self) -> None:
        report = build_agent_gate_report(
            registry_paths=(REGISTRY,),
            agent_id="repo_cli_agent",
            action="read.run_ledger",
            target="run_ledger",
        )
        ledger = [event.to_dict() for event in build_agent_gate_events(report, run_id="run-1", start_sequence=1)]

        audit = build_agent_gate_audit_report(ledger, ledger_source="ledger.jsonl")

        self.assertEqual(audit.status, "needs_evidence")
        self.assertTrue(audit.blocked)
        self.assertEqual(audit.items[0].outcome, "evidence_missing")


if __name__ == "__main__":
    unittest.main()
