from __future__ import annotations

import json
import unittest
from pathlib import Path

from delegation_bot.doctor import render_doctor_report, run_doctor


ROOT = Path(__file__).resolve().parents[1]


class DoctorTests(unittest.TestCase):
    def test_run_doctor_checks_core_control_plane(self) -> None:
        report = run_doctor(ROOT, include_github=False)
        check_ids = {check.id for check in report.checks}

        self.assertEqual(report.failed_count, 0)
        self.assertIn("python", check_ids)
        self.assertIn("dependencies", check_ids)
        self.assertIn("example_harnessfile", check_ids)
        self.assertIn("suggest_loop", check_ids)
        self.assertIn("ledger_fixtures", check_ids)
        self.assertIn('delegation suggest "prepare this repo for release" --plan', report.next_commands)

    def test_render_doctor_report_is_human_readable(self) -> None:
        report = run_doctor(ROOT, include_github=False)
        rendered = render_doctor_report(report)

        self.assertIn("Delegation Doctor", rendered)
        self.assertIn("Status: ready", rendered)
        self.assertIn("Ready:", rendered)
        self.assertIn("Needs attention:", rendered)
        self.assertIn("Next:", rendered)
        self.assertIn("delegation demo", rendered)

    def test_doctor_report_is_json_serializable(self) -> None:
        report = run_doctor(ROOT, include_github=False)

        encoded = json.dumps(report.to_dict(), sort_keys=True)

        self.assertIn("suggest_loop", encoded)


if __name__ == "__main__":
    unittest.main()
