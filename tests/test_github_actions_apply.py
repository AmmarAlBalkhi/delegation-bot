from __future__ import annotations

import copy
import unittest
from pathlib import Path

from delegation_bot.github_actions_apply import (
    ACTIONS_CONFIRMATION,
    build_actions_apply_report,
    render_actions_apply_report,
)
from delegation_bot.harness_manifest import load_manifest
from delegation_bot.harness_plan import build_dry_run_ledger, compile_plan


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "ai-harness-control-plane.yaml"


def example_manifest_and_ledger() -> tuple[dict, object, list[dict]]:
    manifest = load_manifest(EXAMPLE)
    plan = compile_plan(manifest, source=str(EXAMPLE))
    ledger_events = [event.to_dict() for event in build_dry_run_ledger(plan)]
    return manifest, plan, ledger_events


def renumber(events: list[dict]) -> list[dict]:
    copied = copy.deepcopy(events)
    for sequence, event in enumerate(copied, start=1):
        event["sequence"] = sequence
    return copied


class GitHubActionsApplyTests(unittest.TestCase):
    def test_preview_report_is_ready_for_example_ledger(self) -> None:
        manifest, plan, ledger_events = example_manifest_and_ledger()

        report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
        )
        text = render_actions_apply_report(report)

        self.assertFalse(report.blocked)
        self.assertEqual(report.status, "ready")
        self.assertEqual(len(report.drafts), 1)
        self.assertIn("actions/runs/dryrun-gha", report.drafts[0].workflow_run_url)
        self.assertIn("GitHub Actions Apply Gate", text)
        self.assertIn("live workflow dispatch is locked", text)

    def test_live_dispatch_is_locked_even_with_confirmation_and_token(self) -> None:
        manifest, plan, ledger_events = example_manifest_and_ledger()

        report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
            apply=True,
            confirmation=ACTIONS_CONFIRMATION,
            token="fake-token",
        )

        self.assertTrue(report.blocked)
        self.assertIn("dispatch.live_supported", {gate.id for gate in report.gates if gate.status == "blocked"})

    def test_policy_can_require_approval_before_workflow_dispatch(self) -> None:
        manifest, _, ledger_events = example_manifest_and_ledger()
        manifest = copy.deepcopy(manifest)
        manifest["policies"]["approvals"]["required_for"].append("workflow")
        plan = compile_plan(manifest, source=str(EXAMPLE))

        report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
        )

        self.assertTrue(report.blocked)
        self.assertIn("approval.github_actions", {gate.id for gate in report.gates if gate.status == "blocked"})

    def test_approval_evidence_unblocks_workflow_policy_gate(self) -> None:
        manifest, _, _ = example_manifest_and_ledger()
        manifest = copy.deepcopy(manifest)
        manifest["policies"]["approvals"]["required_for"].append("workflow")
        plan = compile_plan(manifest, source=str(EXAMPLE))
        ledger_events = [event.to_dict() for event in build_dry_run_ledger(plan)]
        ledger_events.append(
            {
                "run_id": ledger_events[0]["run_id"],
                "sequence": len(ledger_events) + 1,
                "timestamp": "2026-07-05T10:00:00+00:00",
                "type": "approval.granted",
                "status": "approved",
                "message": "Approved workflow dispatch preview.",
                "action_id": "executor.verification_runner",
                "details": {"approver": "AmmarAlBalkhi", "adapter": "github.actions"},
            }
        )

        report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
        )

        approval_gates = [gate for gate in report.gates if gate.id == "approval.github_actions"]
        self.assertEqual(approval_gates[0].status, "passed")
        self.assertFalse(report.blocked)

    def test_missing_workflow_evidence_blocks_even_when_other_adapter_evidence_exists(self) -> None:
        manifest, plan, ledger_events = example_manifest_and_ledger()
        ledger_events = renumber(
            [
                event
                for event in ledger_events
                if event.get("action_id") != "executor.verification_runner"
            ]
        )

        report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
        )

        self.assertTrue(report.blocked)
        self.assertIn("ledger.github_actions_evidence", {gate.id for gate in report.gates if gate.status == "blocked"})


if __name__ == "__main__":
    unittest.main()
