from __future__ import annotations

import unittest
from pathlib import Path

from delegation_bot.evals import run_declared_evals
from delegation_bot.harness_manifest import load_manifest
from delegation_bot.harness_plan import build_dry_run_ledger, compile_plan
from delegation_bot.playbook_catalog import catalog_facets, filter_catalog, load_catalog, summarize_catalog, validate_catalog


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "playbooks" / "catalog.yaml"


class PlaybookCatalogTests(unittest.TestCase):
    def test_catalog_validates_and_summarizes(self) -> None:
        catalog = load_catalog(CATALOG)

        self.assertEqual(validate_catalog(catalog, ROOT), [])
        self.assertIn("playbook-code-review", summarize_catalog(catalog))

    def test_catalog_filters_by_tag_and_adapter(self) -> None:
        catalog = load_catalog(CATALOG)

        filtered, catalog_filter = filter_catalog(catalog, tags=["release"], adapters=["github.actions"])

        self.assertEqual(catalog_filter.tags, ("release",))
        self.assertEqual(catalog_filter.adapters, ("github.actions",))
        self.assertEqual([entry["id"] for entry in filtered["playbooks"]], ["playbook-release-readiness"])
        self.assertIn("Matches: 1", summarize_catalog(filtered, catalog_filter=catalog_filter))

    def test_catalog_filters_can_return_no_matches(self) -> None:
        catalog = load_catalog(CATALOG)

        filtered, catalog_filter = filter_catalog(catalog, tags=["release"], adapters=["claude.code"])

        self.assertEqual(filtered["playbooks"], [])
        self.assertIn("- none", summarize_catalog(filtered, catalog_filter=catalog_filter))

    def test_catalog_facets_list_available_tags_and_adapters(self) -> None:
        catalog = load_catalog(CATALOG)
        facets = catalog_facets(catalog)

        self.assertIn("release", facets["tags"])
        self.assertIn("github.issue", facets["adapters"])

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
