"""Release readiness checks for DelegationHQ."""

from __future__ import annotations

import subprocess
import sys
import tomllib
import typing as T
from dataclasses import dataclass, field
from pathlib import Path

from delegation_bot import __version__
from delegation_bot.release_artifacts import DEFAULT_CHECKSUMS_NAME, DEFAULT_MANIFEST_NAME, verify_artifact_outputs


ROOT = Path(__file__).resolve().parents[1]
READY = "ready"
WARNING = "warning"
FAILED = "failed"


@dataclass(frozen=True)
class ReleaseCheck:
    id: str
    title: str
    status: str
    message: str
    details: list[str] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, T.Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class ReleaseReadinessReport:
    checks: list[ReleaseCheck]
    next_commands: list[str]

    @property
    def failed_count(self) -> int:
        return sum(1 for check in self.checks if check.status == FAILED)

    @property
    def warning_count(self) -> int:
        return sum(1 for check in self.checks if check.status == WARNING)

    @property
    def ready_count(self) -> int:
        return sum(1 for check in self.checks if check.status == READY)

    @property
    def status(self) -> str:
        if self.failed_count:
            return FAILED
        if self.warning_count:
            return WARNING
        return READY

    def to_dict(self) -> dict[str, T.Any]:
        return {
            "status": self.status,
            "version": __version__,
            "ready_count": self.ready_count,
            "warning_count": self.warning_count,
            "failed_count": self.failed_count,
            "checks": [check.to_dict() for check in self.checks],
            "next_commands": self.next_commands,
        }


def build_release_readiness_report(root: Path = ROOT, *, strict_artifacts: bool = False) -> ReleaseReadinessReport:
    checks = [
        _check_package_metadata(root),
        _check_license_notice(root),
        _check_core_docs(root),
        _check_changelog(root),
        _check_ci_release_evidence(root),
        _check_package_smoke(root),
        _check_windows_packaging(root),
        _check_git_state(root),
        _check_artifacts(root, strict_artifacts=strict_artifacts),
    ]
    return ReleaseReadinessReport(checks=checks, next_commands=_next_commands(checks))


def render_release_readiness_report(report: ReleaseReadinessReport) -> str:
    lines = [
        "Release Readiness",
        "",
        f"Status: {report.status}",
        f"Version: {__version__}",
        f"Ready checks: {report.ready_count}/{len(report.checks)}",
        f"Needs attention: {report.warning_count + report.failed_count}",
        "",
        "Next:",
    ]
    for command in report.next_commands:
        lines.append(f"- {command}")

    for section, status in (("Ready", READY), ("Warnings", WARNING), ("Failed", FAILED)):
        matching = [check for check in report.checks if check.status == status]
        lines.extend(["", f"{section}:"])
        if not matching:
            lines.append("- none")
            continue
        for check in matching:
            lines.append(f"- {check.title}: {check.message}")
            for detail in check.details:
                lines.append(f"  detail: {detail}")
            if check.next_action:
                lines.append(f"  next: {check.next_action}")
    return "\n".join(lines)


def _ready(id: str, title: str, message: str, details: list[str] | None = None) -> ReleaseCheck:
    return ReleaseCheck(id=id, title=title, status=READY, message=message, details=details or [])


def _warning(
    id: str,
    title: str,
    message: str,
    *,
    details: list[str] | None = None,
    next_action: str | None = None,
) -> ReleaseCheck:
    return ReleaseCheck(
        id=id,
        title=title,
        status=WARNING,
        message=message,
        details=details or [],
        next_action=next_action,
    )


def _failed(
    id: str,
    title: str,
    message: str,
    *,
    details: list[str] | None = None,
    next_action: str | None = None,
) -> ReleaseCheck:
    return ReleaseCheck(
        id=id,
        title=title,
        status=FAILED,
        message=message,
        details=details or [],
        next_action=next_action,
    )


def _check_package_metadata(root: Path) -> ReleaseCheck:
    pyproject = root / "pyproject.toml"
    try:
        with pyproject.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return _failed("package_metadata", "Package Metadata", "pyproject.toml could not be parsed.", details=[str(exc)])

    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    scripts = project.get("scripts") if isinstance(project.get("scripts"), dict) else {}
    urls = project.get("urls") if isinstance(project.get("urls"), dict) else {}
    optional = project.get("optional-dependencies") if isinstance(project.get("optional-dependencies"), dict) else {}
    exe_deps = optional.get("exe") if isinstance(optional.get("exe"), list) else []
    problems: list[str] = []
    if project.get("name") != "delegationhq":
        problems.append("project.name must be delegationhq")
    if project.get("version") != __version__:
        problems.append(f"project.version must match package version {__version__}")
    if project.get("license") != "Apache-2.0":
        problems.append("project.license must be Apache-2.0")
    if project.get("license-files") != ["LICENSE", "NOTICE"]:
        problems.append("project.license-files must include LICENSE and NOTICE")
    if scripts.get("delegation") != "delegation_bot.cli:main":
        problems.append("project.scripts.delegation must point to delegation_bot.cli:main")
    if "pyinstaller" not in " ".join(str(item).lower() for item in exe_deps):
        problems.append("project.optional-dependencies.exe must include PyInstaller")
    for key in ("Homepage", "Documentation", "Repository", "Issues"):
        if not str(urls.get(key, "")).startswith("https://github.com/AmmarAlBalkhi/delegation-bot"):
            problems.append(f"project.urls.{key} should point at the current GitHub repository until a site is owned")

    if problems:
        return _failed(
            "package_metadata",
            "Package Metadata",
            "Package metadata is not release-ready.",
            details=problems,
            next_action="Fix pyproject.toml, then rerun `delegation release-check`.",
        )
    return _ready("package_metadata", "Package Metadata", f"delegationhq {__version__} metadata is aligned.")


def _check_license_notice(root: Path) -> ReleaseCheck:
    missing = [path for path in (root / "LICENSE", root / "NOTICE") if not path.exists()]
    if missing:
        return _failed(
            "license_notice",
            "License And Notice",
            "Required legal files are missing.",
            details=[str(path.relative_to(root)) for path in missing],
        )
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    notice_text = (root / "NOTICE").read_text(encoding="utf-8")
    problems: list[str] = []
    if "Apache License" not in license_text or "Version 2.0" not in license_text:
        problems.append("LICENSE must contain Apache License Version 2.0 text")
    if "DelegationHQ" not in notice_text or "Ammar Al Balkhi" not in notice_text:
        problems.append("NOTICE must identify DelegationHQ and Ammar Al Balkhi")
    if problems:
        return _failed("license_notice", "License And Notice", "License files need attention.", details=problems)
    return _ready("license_notice", "License And Notice", "Apache-2.0 license and NOTICE are present.")


def _check_core_docs(root: Path) -> ReleaseCheck:
    required = [
        "README.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "docs/demo.md",
        "docs/doctor.md",
        "docs/release.md",
        "docs/qa.md",
        "docs/testpypi-dry-run.md",
        "docs/windows-exe.md",
        "docs/open-core-strategy.md",
    ]
    missing = [path for path in required if not (root / path).exists()]
    if missing:
        return _failed(
            "core_docs",
            "Core Docs",
            "Release-facing docs are missing.",
            details=missing,
            next_action="Restore required release docs before tagging.",
        )
    return _ready("core_docs", "Core Docs", f"{len(required)} release-facing docs are present.")


def _check_changelog(root: Path) -> ReleaseCheck:
    try:
        text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError as exc:
        return _failed("changelog", "Changelog", "CHANGELOG.md could not be read.", details=[str(exc)])
    if f"## {__version__} - Unreleased" not in text:
        return _warning(
            "changelog",
            "Changelog",
            "Current version does not have an unreleased changelog heading.",
            next_action=f"Add `## {__version__} - Unreleased` before release notes are cut.",
        )
    missing_mentions = [needle for needle in ("delegation --version", "delegation release-check") if needle not in text]
    if missing_mentions:
        return _warning(
            "changelog",
            "Changelog",
            "Recent CLI release polish is not mentioned.",
            details=[f"missing `{needle}`" for needle in missing_mentions],
            next_action="Mention release-check/version polish in CHANGELOG.md.",
        )
    return _ready("changelog", "Changelog", f"CHANGELOG.md includes {__version__} release notes.")


def _check_ci_release_evidence(root: Path) -> ReleaseCheck:
    tests_workflow = root / ".github" / "workflows" / "tests.yml"
    delegation_workflow = root / ".github" / "workflows" / "delegation.yml"
    problems: list[str] = []
    try:
        tests_text = tests_workflow.read_text(encoding="utf-8")
        delegation_text = delegation_workflow.read_text(encoding="utf-8")
    except OSError as exc:
        return _failed("ci_release_evidence", "CI Release Evidence", "Workflow files are missing.", details=[str(exc)])
    for needle in ("python scripts/qa.py", "actions/upload-artifact", "docs/release.md", "CHANGELOG.md"):
        if needle not in tests_text:
            problems.append(f"tests.yml missing `{needle}`")
    for needle in ("release-artifacts-manifest.txt", "delegation-run-evidence", "docs/release.md", "CHANGELOG.md"):
        if needle not in delegation_text:
            problems.append(f"delegation.yml missing `{needle}`")
    if problems:
        return _failed(
            "ci_release_evidence",
            "CI Release Evidence",
            "Workflow release evidence is incomplete.",
            details=problems,
        )
    return _ready("ci_release_evidence", "CI Release Evidence", "Workflows upload QA and release evidence artifacts.")


def _check_package_smoke(root: Path) -> ReleaseCheck:
    try:
        text = (root / "scripts" / "package_smoke.py").read_text(encoding="utf-8")
    except OSError as exc:
        return _failed("package_smoke", "Package Smoke", "scripts/package_smoke.py could not be read.", details=[str(exc)])
    problems = [needle for needle in ("--version", "demo", "Status: ready") if needle not in text]
    if problems:
        return _failed(
            "package_smoke",
            "Package Smoke",
            "Installed package smoke does not cover the first-run path.",
            details=[f"missing `{needle}`" for needle in problems],
        )
    return _ready("package_smoke", "Package Smoke", "Installed package smoke checks version and demo.")


def _check_windows_packaging(root: Path) -> ReleaseCheck:
    try:
        build_text = (root / "scripts" / "build-windows-exe.ps1").read_text(encoding="utf-8")
        install_text = (root / "scripts" / "install-windows-exe.ps1").read_text(encoding="utf-8")
        docs_text = (root / "docs" / "windows-exe.md").read_text(encoding="utf-8")
    except OSError as exc:
        return _failed("windows_packaging", "Windows Packaging", "Windows packaging files could not be read.", details=[str(exc)])
    problems: list[str] = []
    for needle in (
        "--version",
        "demo --ledger",
        "init --goal",
        "validate $SmokeHarnessfile",
        "artifacts --dist $ResolvedDistPath",
        "SHA256SUMS.txt",
        "artifacts-manifest.json",
    ):
        if needle not in build_text:
            problems.append(f"build-windows-exe.ps1 missing `{needle}`")
    for needle in ("--version", "doctor --skip-github", "LOCALAPPDATA", "DelegationHQ\\bin"):
        if needle not in install_text:
            problems.append(f"install-windows-exe.ps1 missing `{needle}`")
    for needle in ("delegation.exe --version", "checksums", "artifacts-manifest.json", "tagged commit"):
        if needle not in docs_text:
            problems.append(f"windows-exe.md missing `{needle}`")
    if problems:
        return _failed("windows_packaging", "Windows Packaging", "Windows EXE release path is incomplete.", details=problems)
    return _ready("windows_packaging", "Windows Packaging", "EXE build/install scripts and docs include versioned smoke checks.")


def _check_git_state(root: Path) -> ReleaseCheck:
    result = _run_git(["status", "--short"], cwd=root)
    if result.returncode != 0:
        return _warning(
            "git_state",
            "Git State",
            "Git status could not be checked.",
            details=[result.stderr.strip() or result.stdout.strip()],
        )
    if result.stdout.strip():
        return _warning(
            "git_state",
            "Git State",
            "Working tree has local changes.",
            details=result.stdout.splitlines()[:8],
            next_action="Commit or stash local changes before tagging a release.",
        )
    branch = _run_git(["branch", "--show-current"], cwd=root).stdout.strip() or "detached"
    return _ready("git_state", "Git State", f"Working tree is clean on `{branch}`.")


def _check_artifacts(root: Path, *, strict_artifacts: bool) -> ReleaseCheck:
    executable = root / "dist" / "delegation.exe"
    checksums = root / "dist" / DEFAULT_CHECKSUMS_NAME
    manifest = root / "dist" / DEFAULT_MANIFEST_NAME
    missing = []
    if not executable.exists():
        missing.append("dist/delegation.exe")
    if not checksums.exists():
        missing.append(f"dist/{DEFAULT_CHECKSUMS_NAME}")
    if not manifest.exists():
        missing.append(f"dist/{DEFAULT_MANIFEST_NAME}")
    if not missing:
        maker = _failed if strict_artifacts else _warning
        verification = verify_artifact_outputs(root / "dist")
        if verification.ready:
            return _ready(
                "release_artifacts",
                "Release Artifacts",
                "Windows executable, checksums, and manifest verify locally.",
                details=[artifact.path for artifact in verification.artifacts],
            )
        return maker(
            "release_artifacts",
            "Release Artifacts",
            "Standalone release artifacts exist but verification failed.",
            details=verification.issues,
            next_action="Rerun `delegation artifacts --dist dist`, then `delegation artifacts --dist dist --check`.",
        )
    maker = _failed if strict_artifacts else _warning
    return maker(
        "release_artifacts",
        "Release Artifacts",
        "Standalone release artifacts are not built yet.",
        details=missing,
        next_action=(
            "Run `./scripts/build-windows-exe.ps1 -InstallDependencies`, which writes "
            "SHA256SUMS.txt and artifacts-manifest.json next to the artifact."
        ),
    )


def _run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(["git", *args], 1, "", str(exc))


def _next_commands(checks: list[ReleaseCheck]) -> list[str]:
    if any(check.status == FAILED for check in checks):
        return ["Fix failed checks, then run `delegation release-check` again."]
    commands = [
        "python scripts/qa.py",
        "python scripts/package_smoke.py",
        "delegation release-check --strict-artifacts",
    ]
    if any(check.id == "release_artifacts" and check.status == WARNING for check in checks):
        commands.insert(2, ".\\scripts\\build-windows-exe.ps1 -InstallDependencies")
    return commands
