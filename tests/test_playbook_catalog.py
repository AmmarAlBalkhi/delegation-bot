from __future__ import annotations

import unittest
from pathlib import Path

from delegation_bot.evals import run_declared_evals
from delegation_bot.harness_manifest import load_manifest
from delegation_bot.harness_plan import build_dry_run_ledger, compile_plan
from delegation_bot.playbook_catalog import load_catalog, summarize_catalog, validate_catalog


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "playbooks" / "catalog.yaml"


class PlaybookCatalogTests(unittest.TestCase):
    def test_catalog_validates_and_summarizes(self) -> None:
        catalog = load_catalog(CATALOG)

        self.assertEqual(validate_catalog(catalog, ROOT), [])
        self.assertIn("playbook-code-review", summarize_catalog(catalog))

    def test_catalog_expected_eval_states_match_dry_run_results(self) -> None:
        catalog = load_catalog(CATALOG)

        for entry in catalog["playbooks"]:
            with self.subTest(playbook=entry["id"]):
                manifest = load_manifest(ROOT / entry["path"])
                plan = compile_plan(manifest, source=entry["path"])
                events = build_dry_run_ledger(
                    plan,
                    run_id=f"catalog-{entry['id']}",
                    timestamp="2026-07-04T08:00:00+00:00",
                )
                results = {
                    result.id: result.status
                    for result in run_declared_evals(manifest, [event.to_dict() for event in events])
                }

                for eval_id, expected_state in entry["expected_eval_states"].items():
                    self.assertEqual(results[eval_id], expected_state)


if __name__ == "__main__":
    unittest.main()
