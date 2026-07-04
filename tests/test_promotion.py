from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from delegation_bot.promotion import evaluate_promotions, load_ledger, passed_eval_ids


MANIFEST = {
    "agents": [
        {
            "id": "planner",
            "autonomy_level": "draft",
            "promotion": {
                "next_level": "act",
                "requires_evals": ["approvals_before_risky_actions", "tests_pass_before_pr"],
            },
        },
        {"id": "observer", "autonomy_level": "suggest"},
    ]
}


class PromotionTests(unittest.TestCase):
    def test_passed_eval_ids_reads_eval_result_events(self) -> None:
        events = [
            {
                "type": "eval.result",
                "status": "passed",
                "details": {"eval_id": "tests_pass_before_pr"},
            },
            {
                "type": "eval.result",
                "status": "failed",
                "details": {"eval_id": "approvals_before_risky_actions"},
            },
        ]

        self.assertEqual(passed_eval_ids(events), {"tests_pass_before_pr"})

    def test_promotion_is_blocked_when_required_eval_is_missing(self) -> None:
        decisions = evaluate_promotions(
            MANIFEST,
            [
                {
                    "type": "eval.result",
                    "status": "passed",
                    "details": {"eval_id": "tests_pass_before_pr"},
                }
            ],
        )

        planner = decisions[0]
        self.assertFalse(planner.ready)
        self.assertEqual(planner.missing_evals, ("approvals_before_risky_actions",))

    def test_promotion_is_ready_when_required_evals_pass(self) -> None:
        decisions = evaluate_promotions(
            MANIFEST,
            [
                {
                    "type": "eval.result",
                    "status": "passed",
                    "details": {"eval_id": "tests_pass_before_pr"},
                },
                {
                    "type": "eval.approvals_before_risky_actions",
                    "status": "passed",
                    "details": {},
                },
            ],
        )

        planner = decisions[0]
        self.assertTrue(planner.ready)
        self.assertEqual(planner.reason, "All required evals passed.")

    def test_load_ledger_reads_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.jsonl"
            path.write_text(
                json.dumps({"type": "eval.result", "status": "passed", "details": {"eval_id": "x"}})
                + "\n",
                encoding="utf-8",
            )
            events = load_ledger(path)

        self.assertEqual(events[0]["type"], "eval.result")


if __name__ == "__main__":
    unittest.main()
