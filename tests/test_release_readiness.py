from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from delegation_bot.cli import main
from delegation_bot.release_readiness import (
    FAILED,
    WARNING,
    build_release_readiness_report,
    render_release_readiness_report,
)


ROOT = Path(__file__).resolve().parents[1]


class ReleaseReadinessTests(unittest.TestCase):
    def test_release_readiness_reports_current_repo_without_failed_checks(self) -> None:
        report = build_release_readiness_report(ROOT)
        check_ids = {check.id for check in report.checks}

        self.assertEqual(report.failed_count, 0)
        self.assertIn("package_metadata", check_ids)
        self.assertIn("ci_release_evidence", check_ids)
        self.assertIn("windows_packaging", check_ids)
        self.assertIn("release_artifacts", check_ids)

    def test_render_release_readiness_is_human_readable(self) -> None:
        report = build_release_readiness_report(ROOT)
        rendered = render_release_readiness_report(report)

        self.assertIn("Release Readiness", rendered)
        self.assertIn("Version: 0.1.0a0", rendered)
        self.assertIn("Next:", rendered)
        self.assertIn("Release Artifacts", rendered)

    def test_release_readiness_json_is_serializable(self) -> None:
        report = build_release_readiness_report(ROOT)
        encoded = json.dumps(report.to_dict(), sort_keys=True)

        self.assertIn("package_metadata", encoded)
        self.assertIn("0.1.0a0", encoded)

    def test_strict_artifacts_fails_when_artifacts_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _copy_release_fixture(root)
            report = build_release_readiness_report(root, strict_artifacts=True)
        artifacts = next(check for check in report.checks if check.id == "release_artifacts")

        self.assertEqual(artifacts.status, FAILED)
        self.assertGreater(report.failed_count, 0)

    def test_non_strict_artifacts_warn_when_artifacts_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _copy_release_fixture(root)
            report = build_release_readiness_report(root, strict_artifacts=False)
        artifacts = next(check for check in report.checks if check.id == "release_artifacts")

        self.assertEqual(artifacts.status, WARNING)
        self.assertEqual(report.failed_count, 0)

    def test_release_check_cli_prints_report(self) -> None:
        import io
        from contextlib import redirect_stdout

        with redirect_stdout(io.StringIO()) as output:
            status = main(["release-check"])

        self.assertEqual(status, 0)
        self.assertIn("Release Readiness", output.getvalue())


def _copy_release_fixture(root: Path) -> None:
    files = [
        "README.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "LICENSE",
        "NOTICE",
        "pyproject.toml",
        "scripts/package_smoke.py",
        "scripts/build-windows-exe.ps1",
        "scripts/install-windows-exe.ps1",
        ".github/workflows/tests.yml",
        ".github/workflows/delegation.yml",
        "docs/demo.md",
        "docs/doctor.md",
        "docs/local-first.md",
        "docs/local-app.md",
        "docs/release.md",
        "docs/qa.md",
        "docs/testpypi-dry-run.md",
        "docs/windows-exe.md",
        "docs/open-core-strategy.md",
    ]
    for relative in files:
        source = ROOT / relative
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
