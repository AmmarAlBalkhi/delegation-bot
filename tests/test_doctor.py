from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from delegation_bot.doctor import _check_github_app_auth, render_doctor_report, run_doctor


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

    def test_run_doctor_can_include_github_app_diagnostics(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            report = run_doctor(ROOT, include_github=False, include_github_app=True)
        check_ids = {check.id for check in report.checks}

        self.assertEqual(report.failed_count, 0)
        self.assertIn("github_app_auth", check_ids)
        self.assertTrue(any(check.id == "github_app_auth" and check.status == "warning" for check in report.checks))
        self.assertIn("Optional safer GitHub auth: delegation github-app-plan --mode issue-write", report.next_commands)

    def test_github_app_doctor_reports_partial_config_without_fallback_token(self) -> None:
        check = _check_github_app_auth(
            ROOT,
            env={"DELEGATION_GITHUB_APP_CLIENT_ID": "client-1", "GITHUB_TOKEN": "broad-secret"},
            find_spec=lambda name: object(),
        )

        self.assertEqual(check.status, "warning")
        self.assertIn("DELEGATION_GITHUB_APP_INSTALLATION_ID", check.details)
        self.assertNotIn("broad-secret", str(check.to_dict()))

    def test_github_app_doctor_ready_redacts_private_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / "app.pem"
            key_path.write_text("-----BEGIN PRIVATE KEY-----\nfixture-secret\n-----END PRIVATE KEY-----\n", encoding="utf-8")
            check = _check_github_app_auth(
                ROOT,
                env={
                    "DELEGATION_GITHUB_APP_CLIENT_ID": "client-1",
                    "DELEGATION_GITHUB_APP_INSTALLATION_ID": "123",
                    "DELEGATION_GITHUB_APP_PRIVATE_KEY_PATH": str(key_path),
                },
                find_spec=lambda name: object(),
            )

        data = check.to_dict()
        self.assertEqual(check.status, "ready")
        self.assertIn("token mint: not attempted by doctor", data["details"])
        self.assertIn("private key: path via DELEGATION_GITHUB_APP_PRIVATE_KEY_PATH", data["details"])
        self.assertNotIn("fixture-secret", str(data))

    def test_github_app_doctor_warns_when_signing_dependencies_are_missing(self) -> None:
        check = _check_github_app_auth(
            ROOT,
            env={
                "DELEGATION_GITHUB_APP_CLIENT_ID": "client-1",
                "DELEGATION_GITHUB_APP_INSTALLATION_ID": "123",
                "DELEGATION_GITHUB_APP_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\nfixture\n-----END PRIVATE KEY-----",
            },
            find_spec=lambda name: None if name == "jwt" else object(),
        )

        self.assertEqual(check.status, "warning")
        self.assertIn("PyJWT", check.details)
        self.assertIn("delegationhq[github-app]", check.next_action or "")


if __name__ == "__main__":
    unittest.main()
