from __future__ import annotations

import unittest
from pathlib import Path

from delegation_bot.dashboard import build_dashboard_snapshot, render_dashboard_snapshot
from delegation_bot.harness_manifest import load_manifest
from delegation_bot.ledger import load_ledger_events


ROOT = Path(__file__).resolve().parents[1]


class DashboardSnapshotTests(unittest.TestCase):
    def test_dashboard_snapshot_summarizes_feedback_recovery_fixture(self) -> None:
        events = load_ledger_events(ROOT / "examples" / "ledgers" / "feedback-recovery.jsonl")
        manifest = {
            "id": "feedback-memory-fixture",
            "objective": "Show feedback issue recovery.",
            "policies": {"permissions": {"allowed_repositories": ["AmmarAlBalkhi/delegation-bot"]}},
        }

        snapshot = build_dashboard_snapshot(
            events,
            manifest=manifest,
            source="examples/ledgers/feedback-recovery.jsonl",
        )
        text = render_dashboard_snapshot(snapshot)

        self.assertEqual(snapshot.status, "ready")
        self.assertEqual(snapshot.counts["events"], 8)
        self.assertEqual(snapshot.counts["feedback_items"], 1)
        self.assertEqual(snapshot.feedback[0]["operation"], "resolve")
        self.assertEqual(snapshot.feedback[0]["live_issue_number"], 321)
        self.assertIn("Dashboard snapshot", text)
        self.assertIn("Next safe action", text)
        self.assertIn("required_adapter_evidence: passed", text)

    def test_dashboard_snapshot_uses_harnessfile_agents_when_provided(self) -> None:
        events = load_ledger_events(ROOT / "examples" / "ledgers" / "adapter-good.jsonl")
        manifest = load_manifest(ROOT / "examples" / "ai-harness-control-plane.yaml")

        snapshot = build_dashboard_snapshot(events, manifest=manifest, source="adapter-good.jsonl")

        self.assertEqual(snapshot.mission["id"], "ai-harness-control-plane")
        self.assertGreaterEqual(snapshot.counts["agents"], 1)
        self.assertTrue(any(agent["runtime"] == "openai.agents" for agent in snapshot.agents))


if __name__ == "__main__":
    unittest.main()
