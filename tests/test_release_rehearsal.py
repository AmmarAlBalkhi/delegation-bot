from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from delegation_bot.cli import main
from delegation_bot.release_artifacts import write_artifact_outputs
from delegation_bot.release_rehearsal import build_release_rehearsal, render_release_rehearsal_report


ROOT = Path(__file__).resolve().parents[1]


class ReleaseRehearsalTests(unittest.TestCase):
    def test_rehearsal_writes_evidence_bundle_for_release_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _copy_release_fixture(root)
            dist = root / "dist"
            dist.mkdir()
            (dist / "delegation.exe").write_bytes(b"fake exe")
            write_artifact_outputs(dist)

            report = build_release_rehearsal(
                root,
                output_dir=Path(".delegation/rehearsal"),
                strict_artifacts=True,
            )
            output_dir = root / ".delegation" / "rehearsal"

            self.assertFalse(report.failed)
            self.assertTrue((output_dir / "release-readiness.json").exists())
            self.assertTrue((output_dir / "artifact-verification.json").exists())
            self.assertTrue((output_dir / "next-steps.md").exists())
            artifact_report = json.loads((output_dir / "artifact-verification.json").read_text(encoding="utf-8"))

        self.assertTrue(artifact_report["ready"])
        self.assertEqual(artifact_report["artifacts"][0]["path"], "delegation.exe")

    def test_strict_rehearsal_fails_when_artifacts_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _copy_release_fixture(root)

            report = build_release_rehearsal(
                root,
                output_dir=Path(".delegation/rehearsal"),
                strict_artifacts=True,
            )
            rendered = render_release_rehearsal_report(report)

        self.assertTrue(report.failed)
        self.assertIn("Artifact Verification", rendered)
        self.assertIn("Release Artifacts", rendered)

    def test_cli_writes_rehearsal_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "bundle"
            with redirect_stdout(io.StringIO()) as output:
                status = main(["release-rehearse", "--output", str(output_dir)])

            self.assertEqual(status, 0)
            self.assertTrue((output_dir / "rehearsal-report.json").exists())
            self.assertIn("Release Rehearsal", output.getvalue())


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
