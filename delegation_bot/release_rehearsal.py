"""Local release rehearsal evidence bundles."""

from __future__ import annotations

import json
import subprocess
import typing as T
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from delegation_bot import __version__
from delegation_bot.release_artifacts import (
    ArtifactVerificationReport,
    render_artifact_verification_report,
    verify_artifact_outputs,
)
from delegation_bot.release_readiness import (
    FAILED,
    READY,
    WARNING,
    ReleaseReadinessReport,
    build_release_readiness_report,
    render_release_readiness_report,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path(".delegation") / "release-rehearsal"


@dataclass(frozen=True)
class EvidenceFile:
    path: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "description": self.description}


@dataclass(frozen=True)
class ReleaseRehearsalReport:
    status: str
    generated_at: str
    version: str
    output_dir: Path
    strict_artifacts: bool
    branch: str
    commit: str
    warnings: list[str]
    issues: list[str]
    files: list[EvidenceFile]

    @property
    def failed(self) -> bool:
        return self.status == FAILED

    def to_dict(self) -> dict[str, T.Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "version": self.version,
            "output_dir": str(self.output_dir),
            "strict_artifacts": self.strict_artifacts,
            "branch": self.branch,
            "commit": self.commit,
            "warnings": self.warnings,
            "issues": self.issues,
            "files": [file.to_dict() for file in self.files],
        }


def build_release_rehearsal(
    root: Path = ROOT,
    *,
    output_dir: Path | None = None,
    dist_path: Path | None = None,
    strict_artifacts: bool = False,
) -> ReleaseRehearsalReport:
    """Write a local evidence bundle for release rehearsal."""

    root = root.resolve()
    output_dir = _resolve_under_root(root, output_dir or DEFAULT_OUTPUT)
    dist_path = _resolve_under_root(root, dist_path or Path("dist"))
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_at = _format_timestamp(datetime.now(UTC))
    release_readiness = build_release_readiness_report(root, strict_artifacts=strict_artifacts)
    artifact_verification = verify_artifact_outputs(dist_path)
    branch = _git_text(["branch", "--show-current"], cwd=root).strip() or "unknown"
    commit = _git_text(["rev-parse", "--short", "HEAD"], cwd=root).strip() or "unknown"
    git_status = _git_text(["status", "--short"], cwd=root)

    files: list[EvidenceFile] = []
    files.append(
        _write_text(
            output_dir,
            "release-readiness.txt",
            render_release_readiness_report(release_readiness) + "\n",
            "Human-readable release readiness report.",
        )
    )
    files.append(
        _write_json(
            output_dir,
            "release-readiness.json",
            release_readiness.to_dict(),
            "Machine-readable release readiness report.",
        )
    )
    files.append(
        _write_text(
            output_dir,
            "artifact-verification.txt",
            render_artifact_verification_report(artifact_verification) + "\n",
            "Human-readable release artifact checksum verification.",
        )
    )
    files.append(
        _write_json(
            output_dir,
            "artifact-verification.json",
            artifact_verification.to_dict(),
            "Machine-readable release artifact checksum verification.",
        )
    )
    files.append(
        _write_text(
            output_dir,
            "git-status.txt",
            git_status if git_status else "clean\n",
            "Git working-tree state at rehearsal time.",
        )
    )

    metadata = {
        "generated_at": generated_at,
        "package": "delegationhq",
        "version": __version__,
        "branch": branch,
        "commit": commit,
        "root": str(root),
        "dist_path": str(dist_path),
        "strict_artifacts": strict_artifacts,
    }
    files.append(_write_json(output_dir, "metadata.json", metadata, "Package, git, and rehearsal metadata."))

    status, warnings, issues = _summarize_status(
        release_readiness,
        artifact_verification,
        strict_artifacts=strict_artifacts,
    )
    report = ReleaseRehearsalReport(
        status=status,
        generated_at=generated_at,
        version=__version__,
        output_dir=output_dir,
        strict_artifacts=strict_artifacts,
        branch=branch,
        commit=commit,
        warnings=warnings,
        issues=issues,
        files=[],
    )
    files.append(
        _write_text(
            output_dir,
            "next-steps.md",
            _render_next_steps(report, release_readiness, artifact_verification),
            "Concise maintainer next steps from this rehearsal.",
        )
    )
    files.append(
        _write_text(
            output_dir,
            "README.md",
            _render_bundle_readme(report),
            "What this local evidence bundle contains.",
        )
    )

    report = ReleaseRehearsalReport(
        status=status,
        generated_at=generated_at,
        version=__version__,
        output_dir=output_dir,
        strict_artifacts=strict_artifacts,
        branch=branch,
        commit=commit,
        warnings=warnings,
        issues=issues,
        files=files,
    )
    files.append(
        _write_json(
            output_dir,
            "rehearsal-report.json",
            report.to_dict(),
            "Top-level release rehearsal summary.",
        )
    )
    return ReleaseRehearsalReport(
        status=status,
        generated_at=generated_at,
        version=__version__,
        output_dir=output_dir,
        strict_artifacts=strict_artifacts,
        branch=branch,
        commit=commit,
        warnings=warnings,
        issues=issues,
        files=files,
    )


def render_release_rehearsal_report(report: ReleaseRehearsalReport) -> str:
    lines = [
        "Release Rehearsal",
        "",
        f"Status: {report.status}",
        f"Version: {report.version}",
        f"Output: {report.output_dir}",
        f"Branch: {report.branch}",
        f"Commit: {report.commit}",
        f"Strict artifacts: {'yes' if report.strict_artifacts else 'no'}",
        "",
        "Files:",
    ]
    lines.extend(f"- {file.path}: {file.description}" for file in report.files)
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    if report.issues:
        lines.extend(["", "Issues:"])
        lines.extend(f"- {issue}" for issue in report.issues)
    if not report.warnings and not report.issues:
        lines.extend(["", "Ready:", "- evidence bundle is ready for release review"])
    return "\n".join(lines)


def _summarize_status(
    release_readiness: ReleaseReadinessReport,
    artifact_verification: ArtifactVerificationReport,
    *,
    strict_artifacts: bool,
) -> tuple[str, list[str], list[str]]:
    warnings: list[str] = []
    issues: list[str] = []
    for check in release_readiness.checks:
        if check.status == FAILED:
            issues.append(f"{check.title}: {check.message}")
        elif check.status == WARNING:
            warnings.append(f"{check.title}: {check.message}")

    if artifact_verification.issues:
        target = issues if strict_artifacts else warnings
        target.extend(f"Artifact Verification: {issue}" for issue in artifact_verification.issues)

    if issues:
        return FAILED, warnings, issues
    if warnings:
        return WARNING, warnings, issues
    return READY, warnings, issues


def _render_next_steps(
    report: ReleaseRehearsalReport,
    release_readiness: ReleaseReadinessReport,
    artifact_verification: ArtifactVerificationReport,
) -> str:
    lines = [
        "# Release Rehearsal Next Steps",
        "",
        f"Status: `{report.status}`",
        "",
    ]
    if report.status == READY:
        lines.extend(
            [
                "- Keep this bundle with the local release notes.",
                "- Run the same rehearsal on a clean Windows release host before publishing an executable.",
                "- Compare artifact hashes before attaching files to a release.",
            ]
        )
    else:
        lines.append("- Fix the warnings or issues below, then rerun `delegation release-rehearse`.")

    if release_readiness.next_commands:
        lines.extend(["", "Recommended commands:"])
        lines.extend(f"- `{command}`" for command in release_readiness.next_commands)

    if artifact_verification.issues:
        lines.extend(["", "Artifact verification issues:"])
        lines.extend(f"- {issue}" for issue in artifact_verification.issues)
    return "\n".join(lines) + "\n"


def _render_bundle_readme(report: ReleaseRehearsalReport) -> str:
    return (
        "# DelegationHQ Release Rehearsal Evidence\n\n"
        "This folder is a local evidence bundle. It does not publish, tag, upload, "
        "dispatch workflows, or call live services.\n\n"
        f"- status: `{report.status}`\n"
        f"- version: `{report.version}`\n"
        f"- branch: `{report.branch}`\n"
        f"- commit: `{report.commit}`\n\n"
        "Use `rehearsal-report.json` for automation and `next-steps.md` for the "
        "maintainer-facing checklist.\n"
    )


def _write_text(output_dir: Path, filename: str, text: str, description: str) -> EvidenceFile:
    path = output_dir / filename
    path.write_text(text, encoding="utf-8")
    return EvidenceFile(path=filename, description=description)


def _write_json(output_dir: Path, filename: str, data: T.Any, description: str) -> EvidenceFile:
    path = output_dir / filename
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return EvidenceFile(path=filename, description=description)


def _resolve_under_root(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _git_text(args: list[str], *, cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _format_timestamp(timestamp: datetime) -> str:
    return timestamp.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
