from __future__ import annotations

import unittest
from pathlib import Path

from delegation_bot.agent_passports import build_agent_passport_report, render_agent_passport_report
from delegation_bot.harness_manifest import load_manifest


ROOT = Path(__file__).resolve().parents[1]


class AgentPassportTests(unittest.TestCase):
    def test_harnessfile_agents_become_passports(self) -> None:
        manifest_path = ROOT / "examples" / "ai-harness-control-plane.yaml"
        manifest = load_manifest(manifest_path)

        report = build_agent_passport_report(manifest=manifest, manifest_source=str(manifest_path))
        text = render_agent_passport_report(report)

        self.assertEqual(report.status, "ready")
        self.assertEqual(report.passport_count, 4)
        planner = next(passport for passport in report.passports if passport.id == "planner")
        self.assertEqual(planner.runtime_type, "openai.agents")
        self.assertIn("read.repository", planner.capabilities)
        self.assertIn("local-repository-tools/inspect_repository", planner.allowed_tools)
        self.assertIn("tests_pass_before_pr", planner.promotion_evals)
        self.assertIn("Agent Passport Registry", text)
        self.assertIn("planner: planner", text)

    def test_custom_registry_agents_become_passports(self) -> None:
        registry_path = ROOT / "examples" / "agent-passports.yaml"

        report = build_agent_passport_report(registry_paths=(registry_path,))

        self.assertEqual(report.status, "ready")
        self.assertEqual(report.passport_count, 2)
        crm = next(passport for passport in report.passports if passport.id == "crm_update_agent")
        self.assertEqual(crm.runtime_type, "langgraph.graph")
        self.assertEqual(crm.endpoint["type"], "command")
        self.assertIn("crm.write", crm.required_approvals)
        self.assertIn("crm_diff_summary", crm.evidence_requirements)

    def test_registry_warns_for_high_risk_agent_without_controls(self) -> None:
        report = build_agent_passport_report(
            registry_paths=(ROOT / "tests" / "fixtures" / "high-risk-agent-passports.yaml",)
        )

        self.assertEqual(report.status, "warning")
        self.assertEqual(report.passport_count, 1)
        self.assertIn("High-risk passport has no required approvals.", report.passports[0].warnings)
        self.assertIn("Passport has no evidence requirements.", report.passports[0].warnings)


if __name__ == "__main__":
    unittest.main()
