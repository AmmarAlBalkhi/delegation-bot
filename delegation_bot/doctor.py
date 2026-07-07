"""Local readiness checks for DelegationHQ."""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tomllib
import typing as T
from dataclasses import dataclass, field
from pathlib import Path

from delegation_bot import __version__
from delegation_bot.github_auth import GitHubAuthError, github_app_credentials_from_env
from delegation_bot.harness_manifest import ManifestError, load_manifest, validate_manifest
from delegation_bot.harness_plan import build_dry_run_ledger, compile_plan
from delegation_bot.ledger import load_ledger_events
from delegation_bot.suggest import build_suggestion


ROOT = Path(__file__).resolve().parents[1]
CHECK_READY = "ready"
CHECK_WARNING = "warning"
CHECK_FAILED = "failed"


@dataclass(frozen=True)
class DoctorCheck:
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
class DoctorReport:
    checks: list[DoctorCheck]
    next_commands: list[str]

    @property
    def failed_count(self) -> int:
        return sum(1 for check in self.checks if check.status == CHECK_FAILED)

    @property
    def warning_count(self) -> int:
        return sum(1 for check in self.checks if check.status == CHECK_WARNING)

    @property
    def ready_count(self) -> int:
        return sum(1 for check in self.checks if check.status == CHECK_READY)

    @property
    def status(self) -> str:
        return CHECK_FAILED if self.failed_count else CHECK_READY

    def to_dict(self) -> dict[str, T.Any]:
        return {
            "status": self.status,
            "ready_count": self.ready_count,
            "warning_count": self.warning_count,
            "failed_count": self.failed_count,
            "checks": [check.to_dict() for check in self.checks],
            "next_commands": self.next_commands,
        }


def run_doctor(
    root: Path = ROOT,
    *,
    include_github: bool = True,
    include_github_app: bool = False,
) -> DoctorReport:
    checks = [
        _check_python_version(),
        _check_dependencies(),
        _check_package_metadata(root),
        _check_license_notice(root),
        _check_schema_json(root),
        _check_example_harnessfile(root),
        _check_suggest_loop(),
        _check_ledger_fixtures(root),
        _check_git_repository(root),
    ]
    if include_github:
        checks.append(_check_github_cli(root))
    if include_github_app:
        checks.append(_check_github_app_auth(root))

    next_commands = _next_commands(checks)
    return DoctorReport(checks=checks, next_commands=next_commands)


def render_doctor_report(report: DoctorReport) -> str:
    status_label = "ready" if report.failed_count == 0 else "needs attention"
    lines = [
        "Delegation Doctor",
        "",
        f"Status: {status_label}",
        f"Ready checks: {report.ready_count}/{len(report.checks)}",
        f"Needs attention: {report.warning_count + report.failed_count}",
        "",
        "Next:",
    ]
    for command in report.next_commands:
        lines.append(f"- {command}")

    lines.extend(["", "Ready:"])
    ready_checks = [check for check in report.checks if check.status == CHECK_READY]
    if ready_checks:
        for check in ready_checks:
            lines.append(f"- {check.title}: {check.message}")
    else:
        lines.append("- none")

    attention_checks = [check for check in report.checks if check.status != CHECK_READY]
    lines.extend(["", "Needs attention:"])
    if attention_checks:
        for check in attention_checks:
            prefix = "FAILED" if check.status == CHECK_FAILED else "WARN"
            lines.append(f"- [{prefix}] {check.title}: {check.message}")
            for detail in check.details:
                lines.append(f"  detail: {detail}")
            if check.next_action:
                lines.append(f"  next: {check.next_action}")
    else:
        lines.append("- none")

    return "\n".join(lines)


def _ready(id: str, title: str, message: str, details: list[str] | None = None) -> DoctorCheck:
    return DoctorCheck(id=id, title=title, status=CHECK_READY, message=message, details=details or [])


def _warning(
    id: str,
    title: str,
    message: str,
    *,
    details: list[str] | None = None,
    next_action: str | None = None,
) -> DoctorCheck:
    return DoctorCheck(
        id=id,
        title=title,
        status=CHECK_WARNING,
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
) -> DoctorCheck:
    return DoctorCheck(
        id=id,
        title=title,
        status=CHECK_FAILED,
        message=message,
        details=details or [],
        next_action=next_action,
    )


def _check_python_version() -> DoctorCheck:
    current = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 11):
        return _ready("python", "Python", f"Python {current} satisfies >=3.11.")
    return _failed(
        "python",
        "Python",
        f"Python {current} is too old.",
        next_action="Install Python 3.11 or newer.",
    )


def _check_dependencies() -> DoctorCheck:
    required = {
        "frontmatter": "python-frontmatter",
        "requests": "requests",
        "yaml": "PyYAML",
    }
    missing: list[str] = []
    for module, package in required.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(package)
    if not missing:
        return _ready("dependencies", "Dependencies", "Required Python packages are importable.")
    return _failed(
        "dependencies",
        "Dependencies",
        "Required Python packages are missing.",
        details=missing,
        next_action="Run `python -m pip install -r requirements.txt`.",
    )


def _check_package_metadata(root: Path) -> DoctorCheck:
    pyproject_path = root / "pyproject.toml"
    try:
        with pyproject_path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return _failed(
            "package_metadata",
            "Package Metadata",
            "pyproject.toml could not be parsed.",
            details=[str(exc)],
        )

    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    scripts = project.get("scripts") if isinstance(project.get("scripts"), dict) else {}
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

    if problems:
        return _failed(
            "package_metadata",
            "Package Metadata",
            "Package metadata is not release-ready.",
            details=problems,
            next_action="Fix pyproject.toml, then rerun `delegation doctor`.",
        )
    return _ready("package_metadata", "Package Metadata", "pyproject.toml is consistent.")


def _check_license_notice(root: Path) -> DoctorCheck:
    try:
        license_text = (root / "LICENSE").read_text(encoding="utf-8")
        notice_text = (root / "NOTICE").read_text(encoding="utf-8")
    except OSError as exc:
        return _failed("license_notice", "License And Notice", "License files are missing.", details=[str(exc)])

    problems: list[str] = []
    if "Apache License" not in license_text or "Version 2.0" not in license_text:
        problems.append("LICENSE must contain Apache License Version 2.0 text")
    if "DelegationHQ" not in notice_text or "Ammar Al Balkhi" not in notice_text:
        problems.append("NOTICE must identify DelegationHQ and Ammar Al Balkhi")
    if problems:
        return _failed("license_notice", "License And Notice", "License files need attention.", details=problems)
    return _ready("license_notice", "License And Notice", "Apache-2.0 license files are present.")


def _check_schema_json(root: Path) -> DoctorCheck:
    schema_paths = sorted((root / "schemas").glob("*.json"))
    if not schema_paths:
        return _failed("schemas", "Schemas", "No JSON schema files were found.")
    try:
        for schema_path in schema_paths:
            with schema_path.open("r", encoding="utf-8") as handle:
                json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return _failed("schemas", "Schemas", "A schema file could not be parsed.", details=[str(exc)])
    return _ready("schemas", "Schemas", f"{len(schema_paths)} schema file(s) parse as JSON.")


def _check_example_harnessfile(root: Path) -> DoctorCheck:
    example_path = root / "examples" / "ai-harness-control-plane.yaml"
    try:
        manifest = load_manifest(example_path)
        errors = validate_manifest(manifest)
    except (OSError, json.JSONDecodeError, ManifestError) as exc:
        return _failed(
            "example_harnessfile",
            "Example Harnessfile",
            "The flagship example could not be loaded.",
            details=[str(exc)],
        )
    if errors:
        return _failed(
            "example_harnessfile",
            "Example Harnessfile",
            "The flagship example is invalid.",
            details=errors,
        )
    return _ready("example_harnessfile", "Example Harnessfile", "Flagship Harnessfile validates.")


def _check_suggest_loop() -> DoctorCheck:
    try:
        suggestion = build_suggestion("prepare this repo for release")
        errors = suggestion.validate()
        if errors:
            return _failed("suggest_loop", "Suggest Loop", "Suggested Harnessfile is invalid.", details=errors)
        plan = compile_plan(suggestion.manifest, source="<doctor>")
        ledger_events = build_dry_run_ledger(plan)
    except Exception as exc:  # pragma: no cover - defensive diagnostic surface
        return _failed("suggest_loop", "Suggest Loop", "Suggest/plan/ledger loop failed.", details=[str(exc)])
    if not ledger_events:
        return _failed("suggest_loop", "Suggest Loop", "Dry-run ledger was empty.")
    return _ready(
        "suggest_loop",
        "Suggest Loop",
        f"`delegation suggest` can compile a dry-run plan with {len(plan.actions)} actions.",
    )


def _check_ledger_fixtures(root: Path) -> DoctorCheck:
    fixture_dir = root / "examples" / "ledgers"
    fixture_paths = [
        fixture_dir / "adapter-good.jsonl",
        fixture_dir / "adapter-blocked.jsonl",
        fixture_dir / "adapter-failed.jsonl",
        fixture_dir / "github-issue-applied.jsonl",
    ]
    problems: list[str] = []
    for fixture_path in fixture_paths:
        try:
            load_ledger_events(fixture_path)
        except Exception as exc:  # pragma: no cover - defensive diagnostic surface
            problems.append(f"{fixture_path.name}: {exc}")
    if problems:
        return _failed("ledger_fixtures", "Ledger Fixtures", "Fixture ledgers could not be read.", details=problems)
    return _ready("ledger_fixtures", "Ledger Fixtures", "Adapter and applied issue fixture ledgers are readable.")


def _check_git_repository(root: Path) -> DoctorCheck:
    git_path = shutil.which("git")
    if not git_path:
        return _warning(
            "git",
            "Git",
            "Git is not available on PATH.",
            next_action="Install Git before publishing branches or releases.",
        )
    result = _run_command([git_path, "rev-parse", "--is-inside-work-tree"], cwd=root)
    if result.returncode != 0 or result.stdout.strip() != "true":
        return _warning("git", "Git", "This directory does not look like a Git worktree.")
    branch = _run_command([git_path, "branch", "--show-current"], cwd=root).stdout.strip() or "detached"
    return _ready("git", "Git", f"Git worktree detected on `{branch}`.")


def _check_github_cli(root: Path) -> DoctorCheck:
    gh_path = shutil.which("gh")
    if not gh_path:
        return _warning(
            "github_cli",
            "GitHub CLI",
            "GitHub CLI is not installed.",
            next_action="Install `gh` before live GitHub apply mode.",
        )
    result = _run_command([gh_path, "auth", "status"], cwd=root)
    if result.returncode == 0:
        return _ready("github_cli", "GitHub CLI", "GitHub CLI is installed and authenticated.")
    return _warning(
        "github_cli",
        "GitHub CLI",
        "GitHub CLI is installed but not authenticated.",
        details=[line for line in (result.stderr or result.stdout).splitlines() if line.strip()][:3],
        next_action="Run `gh auth login` before live GitHub apply mode.",
    )


def _check_github_app_auth(
    root: Path,
    *,
    env: T.Mapping[str, str] | None = None,
    find_spec: T.Callable[[str], T.Any] = importlib.util.find_spec,
) -> DoctorCheck:
    values = env or os.environ
    if not _github_app_env_present(values):
        return _warning(
            "github_app_auth",
            "GitHub App Auth",
            "GitHub App auth is not configured.",
            details=["No DELEGATION_GITHUB_APP_* env vars were found."],
            next_action=(
                "Run `delegation github-app-plan --mode issue-write`, then set GitHub App env vars "
                "before using `--auth github-app`."
            ),
        )

    try:
        credentials, missing = github_app_credentials_from_env(values, cwd=root)
    except GitHubAuthError as exc:
        return _warning(
            "github_app_auth",
            "GitHub App Auth",
            "GitHub App auth config could not be read.",
            details=[str(exc)],
            next_action="Fix the GitHub App env vars, then rerun `delegation doctor --github-app`.",
        )

    if credentials is None:
        return _warning(
            "github_app_auth",
            "GitHub App Auth",
            "GitHub App auth config is incomplete.",
            details=list(missing),
            next_action="Set the missing GitHub App env vars before using `--auth github-app`.",
        )

    missing_packages = _missing_github_app_signing_modules(find_spec)
    if missing_packages:
        return _warning(
            "github_app_auth",
            "GitHub App Auth",
            "GitHub App env vars are present, but signing dependencies are missing.",
            details=missing_packages,
            next_action='Install optional auth support with `pip install "delegationhq[github-app]"`.',
        )

    return _ready(
        "github_app_auth",
        "GitHub App Auth",
        "GitHub App issue-write auth looks locally configured.",
        details=[
            "client id: set",
            "installation id: set",
            f"private key: {_github_app_private_key_source(values)}",
            f"api url: {credentials.api_url}",
            f"api version: {credentials.api_version}",
            "token mint: not attempted by doctor",
        ],
    )


def _github_app_env_present(values: T.Mapping[str, str]) -> bool:
    names = (
        "DELEGATION_GITHUB_APP_CLIENT_ID",
        "GITHUB_APP_CLIENT_ID",
        "DELEGATION_GITHUB_APP_ID",
        "GITHUB_APP_ID",
        "DELEGATION_GITHUB_APP_INSTALLATION_ID",
        "GITHUB_APP_INSTALLATION_ID",
        "DELEGATION_GITHUB_APP_PRIVATE_KEY",
        "GITHUB_APP_PRIVATE_KEY",
        "DELEGATION_GITHUB_APP_PRIVATE_KEY_PATH",
        "GITHUB_APP_PRIVATE_KEY_PATH",
    )
    return any(isinstance(values.get(name), str) and values[name].strip() for name in names)


def _missing_github_app_signing_modules(find_spec: T.Callable[[str], T.Any]) -> list[str]:
    missing: list[str] = []
    if find_spec("jwt") is None:
        missing.append("PyJWT")
    if find_spec("cryptography") is None:
        missing.append("cryptography")
    return missing


def _github_app_private_key_source(values: T.Mapping[str, str]) -> str:
    path_names = ("DELEGATION_GITHUB_APP_PRIVATE_KEY_PATH", "GITHUB_APP_PRIVATE_KEY_PATH")
    for name in path_names:
        value = values.get(name)
        if isinstance(value, str) and value.strip():
            return f"path via {name}"
    return "env var"


def _run_command(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(command, 1, "", str(exc))


def _next_commands(checks: list[DoctorCheck]) -> list[str]:
    if any(check.status == CHECK_FAILED for check in checks):
        return ["Fix failed checks, then run `delegation doctor` again."]
    commands = [
        "delegation demo",
        'delegation init --goal "prepare this repo for safe AI delegation"',
        'delegation suggest "prepare this repo for release" --plan',
    ]
    if any(check.id == "github_cli" and check.status != CHECK_READY for check in checks):
        commands.append(
            "Optional live GitHub: install/authenticate `gh`, or set `GITHUB_TOKEN`/`GH_TOKEN` before apply commands."
        )
    if any(check.id == "github_app_auth" and check.status != CHECK_READY for check in checks):
        commands.append("Optional safer GitHub auth: delegation github-app-plan --mode issue-write")
    return commands
