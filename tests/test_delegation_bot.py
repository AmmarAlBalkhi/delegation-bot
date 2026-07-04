from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import unittest
from unittest import mock
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


class TaskDiscoveryTests(unittest.TestCase):
    def test_task_glob_env_can_point_to_legacy_examples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            legacy_dir = Path(tmp) / "legacy"
            legacy_dir.mkdir()
            task_file = legacy_dir / "weekly-status.md"
            task_file.write_text("---\nid: weekly-status\ntitle: Weekly Status\n---\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {"TASK_GLOB": str(legacy_dir / "*.md")}):
                self.assertEqual(delegation_bot.glob_task_files(), [str(task_file)])


if __name__ == "__main__":
    unittest.main()
