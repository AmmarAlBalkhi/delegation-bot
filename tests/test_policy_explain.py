from __future__ import annotations

import unittest
from pathlib import Path

from delegation_bot.harness_manifest import load_manifest
from delegation_bot.harness_plan import build_dry_run_ledger, compile_plan
from delegation_bot.model_suggest_live import build_live_model_config
from delegation_bot.policy_explain import (
    build_policy_explanation_report,
    extract_classifier_findings,
    render_policy_explanation_report,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "ai-harness-control-plane.yaml"


def example_ledger() -> list[dict]:
    manifest = load_manifest(EXAMPLE)
    plan = compile_plan(manifest, source=str(EXAMPLE))
    return [event.to_dict() for event in build_dry_run_ledger(plan)]


class PolicyExplainTests(unittest.TestCase):
    def test_extracts_local_classifier_findings_from_ledger(self) -> None:
        findings = list(extract_classifier_findings(example_ledger()))

        self.assertTrue(findings)
        self.assertTrue(any(finding.policy_profile == "delegation.default" for finding in findings))
        self.assertTrue(all(finding.recommended_gate for finding in findings))

    def test_deterministic_explanation_keeps_gate_authority_clear(self) -> None:
        report = build_policy_explanation_report(
            example_ledger(),
            ledger_source=".delegation/latest.jsonl",
        )
        text = render_policy_explanation_report(report)

        self.assertEqual(report.status, "ready")
        self.assertIn("Deterministic gates still decide", text)
        self.assertIn("deterministic_ledger_gates", text)

    def test_model_explanation_requires_explicit_opt_in(self) -> None:
        report = build_policy_explanation_report(
            example_ledger(),
            ledger_source=".delegation/latest.jsonl",
            use_model=True,
            allow_live_model=False,
        )

        self.assertTrue(report.blocked)
        self.assertIn("--allow-live-model", report.blocked_reason or "")

    def test_mocked_ollama_explanation_cannot_change_authority(self) -> None:
        def sender(url: str, headers: dict[str, str], payload: dict, timeout_seconds: int) -> dict:
            return {
                "response": (
                    '{"explanation":"This is high because release-like terms matched. '
                    'Deterministic gates remain the authority."}'
                )
            }

        report = build_policy_explanation_report(
            example_ledger(),
            ledger_source=".delegation/latest.jsonl",
            use_model=True,
            allow_live_model=True,
            config=build_live_model_config("ollama", model="llama-test"),
            sender=sender,
        )

        self.assertEqual(report.status, "ready")
        self.assertEqual(report.explanations[0].source, "model")
        self.assertEqual(report.explanations[0].authority, "deterministic_ledger_gates")
        self.assertIn("Deterministic gates remain the authority", report.explanations[0].explanation)


if __name__ == "__main__":
    unittest.main()
