from __future__ import annotations

import unittest
from pathlib import Path

from delegation_bot.evals import run_declared_evals
from delegation_bot.harness_manifest import load_manifest, validate_manifest
from delegation_bot.harness_plan import build_dry_run_ledger, compile_plan


ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_DIR = ROOT / "playbooks"


class PlaybookTests(unittest.TestCase):
    def test_starter_playbooks_validate_compile_and_leave_adapter_evidence(self) -> None:
        playbooks = sorted(PLAYBOOK_DIR.glob("*.yaml"))
        playbooks = [path for path in playbooks if path.name != "catalog.yaml"]

        self.assertGreaterEqual(len(playbooks), 3)
        self.assertEqual(len({path.name for path in playbooks}), len(playbooks))

        manifest_ids: set[str] = set()
        for path in playbooks:
            with self.subTest(playbook=path.name):
                manifest = load_manifest(path)
                self.assertEqual(validate_manifest(manifest), [])
                self.assertNotIn(str(manifest["id"]), manifest_ids)
                manifest_ids.add(str(manifest["id"]))

                plan = compile_plan(manifest, source=str(path))
                self.assertEqual(plan.warnings, ())

                action_types = {action.type for action in plan.actions}
                self.assertIn("adapter.github.issue.prepare", action_types)
                self.assertIn("adapter.sample.echo.prepare", action_types)
                self.assertIn("output.prepare.run_ledger", action_types)
                self.assertIn("eval.schedule", action_types)

                events = build_dry_run_ledger(
                    plan,
                    run_id=f"test-{path.stem}",
                    timestamp="2026-07-04T08:00:00+00:00",
                )
                event_types = {event.type for event in events}
                self.assertIn("github.issue.planned", event_types)
                self.assertIn("sample.echo.planned", event_types)

                results = run_declared_evals(manifest, [event.to_dict() for event in events])
                adapter_evidence = next(
                    result for result in results if result.id == "required_adapter_evidence"
                )
                self.assertEqual(adapter_evidence.status, "passed")


if __name__ == "__main__":
    unittest.main()
