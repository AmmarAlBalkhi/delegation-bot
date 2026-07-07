from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path

from delegation_bot import __version__
from delegation_bot.cli import main
from delegation_bot.release_artifacts import (
    DEFAULT_CHECKSUMS_NAME,
    DEFAULT_MANIFEST_NAME,
    build_artifact_manifest,
    render_sha256sums,
    verify_artifact_outputs,
    write_artifact_outputs,
)


class ReleaseArtifactsTests(unittest.TestCase):
    def test_manifest_hashes_release_artifacts_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dist = Path(tmpdir)
            artifact = dist / "delegation.exe"
            artifact.write_bytes(b"delegation executable")

            manifest = build_artifact_manifest(
                dist,
                generated_at=datetime(2026, 7, 7, 12, 30, tzinfo=UTC),
            )

        digest = hashlib.sha256(b"delegation executable").hexdigest()
        self.assertEqual(manifest.generated_at, "2026-07-07T12:30:00Z")
        self.assertEqual(len(manifest.artifacts), 1)
        self.assertEqual(manifest.artifacts[0].path, "delegation.exe")
        self.assertEqual(manifest.artifacts[0].sha256, digest)
        self.assertEqual(render_sha256sums(manifest), f"{digest}  delegation.exe\n")

    def test_write_outputs_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dist = Path(tmpdir)
            (dist / "delegation.exe").write_bytes(b"stable artifact")

            manifest = write_artifact_outputs(dist)
            report = verify_artifact_outputs(dist)
            manifest_data = json.loads((dist / DEFAULT_MANIFEST_NAME).read_text(encoding="utf-8"))

        self.assertEqual(len(manifest.artifacts), 1)
        self.assertTrue(report.ready)
        self.assertEqual(report.issues, [])
        self.assertEqual(manifest_data["version"], __version__)
        self.assertEqual(manifest_data["artifacts"][0]["path"], "delegation.exe")

    def test_generated_outputs_are_not_rehashed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dist = Path(tmpdir)
            (dist / "delegation.exe").write_bytes(b"release")
            (dist / DEFAULT_CHECKSUMS_NAME).write_text("old\n", encoding="utf-8")
            (dist / DEFAULT_MANIFEST_NAME).write_text("{}\n", encoding="utf-8")

            manifest = build_artifact_manifest(dist)

        self.assertEqual([artifact.path for artifact in manifest.artifacts], ["delegation.exe"])

    def test_verification_catches_stale_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dist = Path(tmpdir)
            artifact = dist / "delegation.exe"
            artifact.write_bytes(b"first")
            write_artifact_outputs(dist)

            artifact.write_bytes(b"second")
            report = verify_artifact_outputs(dist)

        self.assertFalse(report.ready)
        self.assertTrue(any("checksum" in issue for issue in report.issues))

    def test_cli_writes_and_checks_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dist = Path(tmpdir)
            (dist / "delegation.exe").write_bytes(b"cli artifact")

            with redirect_stdout(io.StringIO()) as write_output:
                write_status = main(["artifacts", "--dist", str(dist)])
            with redirect_stdout(io.StringIO()) as check_output:
                check_status = main(["artifacts", "--dist", str(dist), "--check"])

        self.assertEqual(write_status, 0)
        self.assertEqual(check_status, 0)
        self.assertIn("Release Artifacts", write_output.getvalue())
        self.assertIn("Status: ready", check_output.getvalue())


if __name__ == "__main__":
    unittest.main()
