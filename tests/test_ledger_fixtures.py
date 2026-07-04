from __future__ import annotations

import unittest
from pathlib import Path

from delegation_bot.evals import eval_ledger_is_valid, eval_required_adapter_evidence
from delegation_bot.ledger import LedgerFilter, build_ledger_view, load_ledger_events, render_ledger_view


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "ledgers"


class LedgerFixtureTests(unittest.TestCase):
    def test_good_adapter_fixture_passes_required_evidence_eval(self) -> None:
        events = load_ledger_events(FIXTURES / "adapter-good.jsonl")

        self.assertEqual(eval_ledger_is_valid(events).status, "passed")
        self.assertEqual(eval_required_adapter_evidence(events).status, "passed")

    def test_blocked_adapter_fixture_blocks_required_evidence_eval(self) -> None:
        events = load_ledger_events(FIXTURES / "adapter-blocked.jsonl")
        result = eval_required_adapter_evidence(events)

        self.assertEqual(eval_ledger_is_valid(events).status, "passed")
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.details["blocked_results"][0]["adapter"], "sample.echo")

    def test_failed_adapter_fixture_fails_required_evidence_eval(self) -> None:
        events = load_ledger_events(FIXTURES / "adapter-failed.jsonl")
        result = eval_required_adapter_evidence(events)

        self.assertEqual(eval_ledger_is_valid(events).status, "passed")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.details["failed_results"][0]["adapter"], "sample.echo")

    def test_fixture_ledger_views_are_readable_and_filterable(self) -> None:
        events = load_ledger_events(FIXTURES / "adapter-good.jsonl")
        view = build_ledger_view(events, ledger_filter=LedgerFilter(adapter="sample.echo"))
        text = render_ledger_view(view)

        self.assertEqual(view.total_events, 4)
        self.assertEqual(len(view.adapter_evidence), 2)
        self.assertIn("sample.echo", text)
        self.assertIn("echo_hash=fixture-good-echo", text)


if __name__ == "__main__":
    unittest.main()
