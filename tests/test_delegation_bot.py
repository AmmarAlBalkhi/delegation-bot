from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "delegation_bot.py"

sys.modules.setdefault("frontmatter", types.ModuleType("frontmatter"))
sys.modules.setdefault("requests", types.ModuleType("requests"))

spec = importlib.util.spec_from_file_location("delegation_bot", SCRIPT)
delegation_bot = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(delegation_bot)


class SchedulingTests(unittest.TestCase):
    def test_future_date_active_is_skipped(self) -> None:
        should_run, reason = delegation_bot.should_run_spec(
            {"id": "future", "interval": "daily", "date_active": "2026-02-01"},
            date(2026, 1, 31),
        )

        self.assertFalse(should_run)
        self.assertIn("starts on 2026-02-01", reason)

    def test_every_interval_runs_on_cadence_day(self) -> None:
        should_run, reason = delegation_bot.should_run_spec(
            {"id": "cadence", "interval": "every:3", "start": "2026-01-01"},
            date(2026, 1, 10),
        )

        self.assertTrue(should_run)
        self.assertIsNone(reason)

    def test_every_interval_skips_off_cadence_day(self) -> None:
        should_run, reason = delegation_bot.should_run_spec(
            {"id": "cadence", "interval": "every:3", "start": "2026-01-01"},
            date(2026, 1, 11),
        )

        self.assertFalse(should_run)
        self.assertIn("not due for every:3", reason)


class ProjectConfigTests(unittest.TestCase):
    def test_project_title_accepts_string(self) -> None:
        self.assertEqual(
            delegation_bot.project_title("Delegation Bot - PoC"),
            "Delegation Bot - PoC",
        )

    def test_project_title_accepts_mapping(self) -> None:
        self.assertEqual(
            delegation_bot.project_title({"owner": "ammar-uni", "title": "Delegation Bot - PoC"}),
            "Delegation Bot - PoC",
        )


if __name__ == "__main__":
    unittest.main()
