from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from delegation_bot import __version__
from delegation_bot.cli import main as package_main
from scripts.delegation import main as script_main


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "ai-harness-control-plane.yaml"


class PackageNamespaceTests(unittest.TestCase):
    def test_package_version_is_available(self) -> None:
        self.assertEqual(__version__, "0.1.0a0")

    def test_package_cli_entrypoint_works(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = package_main(["validate", str(EXAMPLE)])

        self.assertEqual(status, 0)
        self.assertIn("Harnessfile: ai-harness-control-plane", output.getvalue())

    def test_script_cli_wrapper_still_works(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = script_main(["adapters", "codex.thread"])

        self.assertEqual(status, 0)
        self.assertIn("codex.thread", output.getvalue())


if __name__ == "__main__":
    unittest.main()
