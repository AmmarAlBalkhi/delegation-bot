from __future__ import annotations

import unittest
from pathlib import Path

from delegation_bot.agent_gate import build_agent_gate_report, render_agent_gate_report
from delegation_bot.harness_manifest import load_manifest


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


if __name__ == "__main__":
    unittest.main()
