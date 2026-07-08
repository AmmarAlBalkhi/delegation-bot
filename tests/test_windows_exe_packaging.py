from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WindowsExePackagingTests(unittest.TestCase):
    def test_build_script_declares_safe_pyinstaller_shape(self) -> None:
        text = (ROOT / "scripts" / "build-windows-exe.ps1").read_text(encoding="utf-8")

        self.assertIn("-m\", \"PyInstaller", text)
        self.assertIn("\"--onefile\"", text)
        self.assertIn("\"--console\"", text)
        self.assertIn("\"--copy-metadata\", \"delegationhq\"", text)
        self.assertIn("scripts\\delegation.py", text)
        self.assertIn("--version", text)
        self.assertIn("demo --ledger", text)
        self.assertIn("init --goal", text)
        self.assertIn("validate $SmokeHarnessfile", text)
        self.assertIn("workspace-init --path $SmokeWorkspace", text)
        self.assertIn("workspace-status --path $SmokeWorkspace", text)
        self.assertIn("agent-add exe_cli_agent --workspace $SmokeWorkspace", text)
        self.assertIn("agent-run exe_cli_agent --workspace $SmokeWorkspace", text)
        self.assertIn("app-plan", text)
        self.assertIn("app-state --workspace $SmokeWorkspace", text)
        self.assertIn("cockpit --workspace $SmokeWorkspace", text)
        self.assertIn("app-dashboard --workspace $SmokeWorkspace", text)
        self.assertIn("timeline --workspace $SmokeWorkspace", text)
        self.assertIn("approval-preview exe_cli_agent --workspace $SmokeWorkspace", text)
        self.assertIn("app-export --workspace $SmokeWorkspace", text)
        self.assertIn("app-serve --workspace $SmokeWorkspace --dry-run", text)
        self.assertIn("agents \"examples\\ai-harness-control-plane.yaml\"", text)
        self.assertIn("agent-gate \"examples\\ai-harness-control-plane.yaml\" implementer", text)
        self.assertIn("agent-audit --ledger", text)
        self.assertIn("approval-inbox --ledger", text)
        self.assertIn("approval-decision --ledger", text)
        self.assertIn("agent-result-ingest --ledger", text)
        self.assertIn("evidence-ingest --ledger", text)
        self.assertIn("runprint-ingest --ledger", text)
        self.assertIn("examples\\agent-passports.yaml", text)
        self.assertIn("artifacts --dist $ResolvedDistPath", text)
        self.assertIn("SHA256SUMS.txt", text)
        self.assertIn("artifacts-manifest.json", text)

    def test_build_script_bundles_runtime_assets(self) -> None:
        text = (ROOT / "scripts" / "build-windows-exe.ps1").read_text(encoding="utf-8")

        for folder in ("examples", "playbooks", "schemas"):
            self.assertIn(f'Source = "{folder}"', text)
            self.assertIn(f'Dest = "{folder}"', text)
        for filename in ("LICENSE", "NOTICE", "README.md"):
            self.assertIn(f'Source = "{filename}"', text)

    def test_generated_packaging_artifacts_are_ignored(self) -> None:
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

        for pattern in ("build/", "dist/", "*.egg-info/"):
            self.assertIn(pattern, ignored)

    def test_docs_explain_windows_exe_build_script(self) -> None:
        text = (ROOT / "docs" / "windows-exe.md").read_text(encoding="utf-8")

        self.assertIn("scripts\\build-windows-exe.ps1", text)
        self.assertIn("scripts\\install-windows-exe.ps1", text)
        self.assertIn("delegation.exe", text)
        self.assertIn("--version", text)
        self.assertIn("demo", text)
        self.assertIn("validate", text)
        self.assertIn("workspace-init", text)
        self.assertIn("workspace-status", text)
        self.assertIn("agent-add", text)
        self.assertIn("agent-run", text)
        self.assertIn("app-plan", text)
        self.assertIn("app-state", text)
        self.assertIn("cockpit", text)
        self.assertIn("app-dashboard", text)
        self.assertIn("timeline", text)
        self.assertIn("approval-preview", text)
        self.assertIn("app-export", text)
        self.assertIn("app-serve", text)
        self.assertIn("agents", text)
        self.assertIn("agent-gate", text)
        self.assertIn("agent-audit", text)
        self.assertIn("approval-inbox", text)
        self.assertIn("approval-decision", text)
        self.assertIn("agent-result-ingest", text)
        self.assertIn("evidence-ingest", text)
        self.assertIn("runprint-ingest", text)
        self.assertIn("SHA256SUMS.txt", text)
        self.assertIn("artifacts-manifest.json", text)

    def test_user_local_install_script_is_non_admin_and_path_aware(self) -> None:
        text = (ROOT / "scripts" / "install-windows-exe.ps1").read_text(encoding="utf-8")

        self.assertIn("$env:LOCALAPPDATA", text)
        self.assertIn("DelegationHQ", text)
        self.assertIn("Copy-Item", text)
        self.assertIn("[Environment]::SetEnvironmentVariable", text)
        self.assertIn("\"User\"", text)
        self.assertIn("delegation.exe --version", text)
        self.assertIn("delegation.exe doctor --skip-github", text)


if __name__ == "__main__":
    unittest.main()
