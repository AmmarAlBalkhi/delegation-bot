"""Release artifact checksum and manifest helpers."""

from __future__ import annotations

import hashlib
import json
import typing as T
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from delegation_bot import __version__


SCHEMA_VERSION = "delegationhq.release-artifacts.v1"
PACKAGE_NAME = "delegationhq"
DEFAULT_CHECKSUMS_NAME = "SHA256SUMS.txt"
DEFAULT_MANIFEST_NAME = "artifacts-manifest.json"
ARTIFACT_SUFFIXES = (".exe", ".msi", ".zip", ".whl", ".tar.gz")
GENERATED_NAMES = {DEFAULT_CHECKSUMS_NAME, DEFAULT_MANIFEST_NAME}


class ArtifactError(RuntimeError):
    """Raised when release artifacts cannot be generated or verified."""


@dataclass(frozen=True)
class ArtifactRecord:
    path: str
    sha256: str
    size_bytes: int

    def to_dict(self) -> dict[str, T.Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class ArtifactManifest:
    generated_at: str
    artifacts: list[ArtifactRecord]

    def to_dict(self) -> dict[str, T.Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "package": PACKAGE_NAME,
            "version": __version__,
            "generated_at": self.generated_at,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }


@dataclass(frozen=True)
class ArtifactVerificationReport:
    dist_path: Path
    artifacts: list[ArtifactRecord]
    issues: list[str]

    @property
    def ready(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, T.Any]:
        return {
            "dist_path": str(self.dist_path),
            "ready": self.ready,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "issues": self.issues,
        }


def build_artifact_manifest(
    dist_path: Path,
    *,
    generated_at: datetime | None = None,
) -> ArtifactManifest:
    """Build a manifest for release artifacts found under a dist directory."""

    dist_path = dist_path.resolve()
    if not dist_path.exists():
        raise ArtifactError(f"Artifact directory does not exist: {dist_path}")
    if not dist_path.is_dir():
        raise ArtifactError(f"Artifact path is not a directory: {dist_path}")

    artifacts = [_record_artifact(path, dist_path=dist_path) for path in _iter_artifact_files(dist_path)]
    if not artifacts:
        raise ArtifactError(f"No release artifacts found in: {dist_path}")

    timestamp = generated_at or datetime.now(UTC)
    return ArtifactManifest(generated_at=_format_timestamp(timestamp), artifacts=artifacts)


def write_artifact_outputs(
    dist_path: Path,
    *,
    checksums_name: str = DEFAULT_CHECKSUMS_NAME,
    manifest_name: str = DEFAULT_MANIFEST_NAME,
) -> ArtifactManifest:
    """Write checksum and JSON manifest files next to release artifacts."""

    manifest = build_artifact_manifest(dist_path)
    dist_path = dist_path.resolve()
    (dist_path / checksums_name).write_text(render_sha256sums(manifest), encoding="utf-8")
    (dist_path / manifest_name).write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def verify_artifact_outputs(
    dist_path: Path,
    *,
    checksums_name: str = DEFAULT_CHECKSUMS_NAME,
    manifest_name: str = DEFAULT_MANIFEST_NAME,
) -> ArtifactVerificationReport:
    """Verify generated checksum and manifest files against current artifacts."""

    issues: list[str] = []
    artifacts: list[ArtifactRecord] = []
    try:
        manifest = build_artifact_manifest(dist_path)
        artifacts = manifest.artifacts
    except ArtifactError as exc:
        return ArtifactVerificationReport(dist_path=dist_path, artifacts=[], issues=[str(exc)])

    dist_path = dist_path.resolve()
    expected_by_path = {artifact.path: artifact for artifact in artifacts}

    checksums_path = dist_path / checksums_name
    if not checksums_path.exists():
        issues.append(f"missing {checksums_path.name}")
    else:
        issues.extend(_verify_checksum_file(checksums_path, dist_path=dist_path, expected_by_path=expected_by_path))

    manifest_path = dist_path / manifest_name
    if not manifest_path.exists():
        issues.append(f"missing {manifest_path.name}")
    else:
        issues.extend(_verify_manifest_file(manifest_path, expected_by_path=expected_by_path))

    return ArtifactVerificationReport(dist_path=dist_path, artifacts=artifacts, issues=issues)


def render_sha256sums(manifest: ArtifactManifest) -> str:
    lines = [f"{artifact.sha256}  {artifact.path}" for artifact in manifest.artifacts]
    return "\n".join(lines) + "\n"


def render_artifact_manifest(manifest: ArtifactManifest, *, dist_path: Path) -> str:
    lines = [
        "Release Artifacts",
        "",
        f"Dist: {dist_path}",
        f"Version: {__version__}",
        f"Artifacts: {len(manifest.artifacts)}",
        "",
        "Written:",
        f"- {Path(dist_path) / DEFAULT_CHECKSUMS_NAME}",
        f"- {Path(dist_path) / DEFAULT_MANIFEST_NAME}",
        "",
        "Files:",
    ]
    for artifact in manifest.artifacts:
        lines.append(f"- {artifact.path} ({artifact.size_bytes} bytes, sha256 {artifact.sha256[:12]}...)")
    return "\n".join(lines)


def render_artifact_verification_report(report: ArtifactVerificationReport) -> str:
    lines = [
        "Release Artifact Verification",
        "",
        f"Status: {'ready' if report.ready else 'failed'}",
        f"Dist: {report.dist_path}",
        f"Artifacts: {len(report.artifacts)}",
    ]
    if report.issues:
        lines.extend(["", "Issues:"])
        lines.extend(f"- {issue}" for issue in report.issues)
    else:
        lines.extend(["", "Ready:", "- checksums and manifest match current artifacts"])
    return "\n".join(lines)


def _iter_artifact_files(dist_path: Path) -> list[Path]:
    paths: list[Path] = []
    for path in dist_path.rglob("*"):
        if not path.is_file():
            continue
        if path.name in GENERATED_NAMES:
            continue
        if _is_release_artifact(path):
            paths.append(path)
    return sorted(paths, key=lambda item: item.relative_to(dist_path).as_posix())


def _is_release_artifact(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(suffix) for suffix in ARTIFACT_SUFFIXES)


def _record_artifact(path: Path, *, dist_path: Path) -> ArtifactRecord:
    relative = path.relative_to(dist_path).as_posix()
    return ArtifactRecord(path=relative, sha256=_sha256_file(path), size_bytes=path.stat().st_size)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _format_timestamp(timestamp: datetime) -> str:
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _verify_checksum_file(
    checksums_path: Path,
    *,
    dist_path: Path,
    expected_by_path: dict[str, ArtifactRecord],
) -> list[str]:
    issues: list[str] = []
    seen: set[str] = set()
    for line_number, line in enumerate(checksums_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            issues.append(f"{checksums_path.name}:{line_number} is not a sha256sum line")
            continue
        checksum, relative_path = parts[0].strip(), parts[1].strip()
        if len(checksum) != 64 or any(char not in "0123456789abcdefABCDEF" for char in checksum):
            issues.append(f"{checksums_path.name}:{line_number} has an invalid sha256 digest")
            continue
        expected = expected_by_path.get(relative_path)
        if expected is None:
            issues.append(f"{checksums_path.name}:{line_number} references unknown artifact {relative_path}")
            continue
        seen.add(relative_path)
        if checksum.lower() != expected.sha256:
            issues.append(f"{relative_path} checksum does not match current artifact")
    missing = sorted(set(expected_by_path) - seen)
    issues.extend(f"{checksums_path.name} missing {path}" for path in missing)
    return issues


def _verify_manifest_file(manifest_path: Path, *, expected_by_path: dict[str, ArtifactRecord]) -> list[str]:
    issues: list[str] = []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{manifest_path.name} is not valid JSON: {exc}"]

    if data.get("schema_version") != SCHEMA_VERSION:
        issues.append(f"{manifest_path.name} has an unexpected schema_version")
    if data.get("package") != PACKAGE_NAME:
        issues.append(f"{manifest_path.name} has an unexpected package")
    if data.get("version") != __version__:
        issues.append(f"{manifest_path.name} version does not match {__version__}")

    entries = data.get("artifacts")
    if not isinstance(entries, list):
        return [*issues, f"{manifest_path.name} artifacts must be a list"]

    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            issues.append(f"{manifest_path.name} artifact {index} must be an object")
            continue
        path = entry.get("path")
        expected = expected_by_path.get(path) if isinstance(path, str) else None
        if expected is None:
            issues.append(f"{manifest_path.name} references unknown artifact {path!r}")
            continue
        seen.add(path)
        if entry.get("sha256") != expected.sha256:
            issues.append(f"{manifest_path.name} checksum for {path} does not match current artifact")
        if entry.get("size_bytes") != expected.size_bytes:
            issues.append(f"{manifest_path.name} size for {path} does not match current artifact")

    missing = sorted(set(expected_by_path) - seen)
    issues.extend(f"{manifest_path.name} missing {path}" for path in missing)
    return issues
