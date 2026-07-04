from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from delegation_bot.adapter_fixtures import build_adapter_fixture, fixture_filename, write_jsonl
from delegation_bot.builtin_adapters import list_builtin_adapters
from delegation_bot.evals import eval_ledger_is_valid, eval_required_adapter_evidence
from delegation_bot.ledger import LedgerFilter, build_ledger_view, load_ledger_events


class AdapterFixtureGeneratorTests(unittest.TestCase):
    def test_generated_fixtures_match_required_evidence_states(self) -> None:
        adapters = [adapter.contract.id for adapter in list_builtin_adapters()]

        for adapter_id in adapters:
            for state, expected_status in (
                ("good", "passed"),
                ("blocked", "blocked"),
                ("failed", "failed"),
            ):
                with self.subTest(adapter=adapter_id, state=state):
                    events = build_adapter_fixture(adapter_id, state)
                    result = eval_required_adapter_evidence(events)

                    self.assertEqual(eval_ledger_is_valid(events).status, "passed")
                    self.assertEqual(result.status, expected_status)

    def test_generated_fixture_can_be_written_and_read_by_ledger_viewer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / fixture_filename("mcp.tool", "good")
            write_jsonl(build_adapter_fixture("mcp.tool", "good"), path)
            events = load_ledger_events(path)

        view = build_ledger_view(events, ledger_filter=LedgerFilter(adapter="mcp.tool"))

        self.assertEqual(view.total_events, 4)
        self.assertEqual(len(view.adapter_evidence), 2)
        self.assertEqual(view.adapter_evidence[0].adapter, "mcp.tool")


if __name__ == "__main__":
    unittest.main()
