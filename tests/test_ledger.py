from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from delegation_bot.ledger import LedgerFilter, build_ledger_view, load_ledger_events, render_ledger_view


SAMPLE_EVENTS = [
    {
        "run_id": "dryrun-demo",
        "sequence": 1,
        "timestamp": "2026-07-04T00:00:00+00:00",
        "type": "plan.compiled",
        "status": "planned",
        "message": "Compiled plan.",
        "action_id": None,
        "details": {},
    },
    {
        "run_id": "dryrun-demo",
        "sequence": 2,
        "timestamp": "2026-07-04T00:00:00+00:00",
        "type": "github.issue.planned",
        "status": "planned",
        "message": "Planned issue.",
        "action_id": "executor.issue_planner",
        "details": {
            "adapter": "github.issue",
            "issue_marker": "delegation-bot:abc123",
            "adapter_result": {
                "status": "planned",
                "message": "Dry-run planned.",
                "outputs": {"github.issue": {"title": "Demo"}},
                "evidence": {"issue_marker": "delegation-bot:abc123"},
                "dry_run": True,
            },
        },
    },
    {
        "run_id": "dryrun-demo",
        "sequence": 3,
        "timestamp": "2026-07-04T00:00:00+00:00",
        "type": "eval.result",
        "status": "passed",
        "message": "Ledger is valid.",
        "action_id": None,
        "details": {
            "eval_id": "ledger_is_valid",
            "eval": {"id": "ledger_is_valid", "status": "passed"},
        },
    },
]


class LedgerViewTests(unittest.TestCase):
    def test_load_ledger_events_reads_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.jsonl"
            path.write_text(
                "\n".join(json.dumps(event) for event in SAMPLE_EVENTS) + "\n",
                encoding="utf-8",
            )

            events = load_ledger_events(path)

        self.assertEqual(len(events), 3)
        self.assertEqual(events[1]["type"], "github.issue.planned")

    def test_build_ledger_view_summarizes_adapters_evals_and_statuses(self) -> None:
        view = build_ledger_view(SAMPLE_EVENTS, source="ledger.jsonl")

        self.assertEqual(view.total_events, 3)
        self.assertEqual(view.status_counts, {"passed": 1, "planned": 2})
        self.assertEqual(view.adapter_counts, {"github.issue": 1})
        self.assertEqual(view.adapter_evidence[0].evidence["issue_marker"], "delegation-bot:abc123")
        self.assertEqual(view.eval_evidence[0].eval_id, "ledger_is_valid")

    def test_ledger_filters_recent_events(self) -> None:
        view = build_ledger_view(
            SAMPLE_EVENTS,
            ledger_filter=LedgerFilter(adapter="github.issue"),
            limit=10,
        )

        self.assertEqual(len(view.shown_events), 1)
        self.assertEqual(view.shown_events[0]["type"], "github.issue.planned")
        self.assertEqual(len(view.adapter_evidence), 1)
        self.assertEqual(view.adapter_evidence[0].adapter, "github.issue")
        self.assertEqual(view.eval_evidence, ())
        self.assertTrue(view.filters.is_active())

    def test_render_ledger_view_is_readable(self) -> None:
        view = build_ledger_view(SAMPLE_EVENTS, source="ledger.jsonl")
        text = render_ledger_view(view)

        self.assertIn("Ledger report", text)
        self.assertIn("Adapter evidence", text)
        self.assertIn("github.issue", text)
        self.assertIn("issue_marker=delegation-bot:abc123", text)
        self.assertIn("ledger_is_valid: passed", text)


if __name__ == "__main__":
    unittest.main()
