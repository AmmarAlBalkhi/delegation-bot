#!/usr/bin/env python3
"""Create a timestamped source backup outside the repository."""

from __future__ import annotations

import argparse
import os
import typing as T
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_DIR = ROOT.parent / "backups"
EXCLUDED_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def iter_backup_files(root: Path) -> T.Iterator[Path]:
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIRS]
        current = Path(current_root)
        for filename in filenames:
            path = current / filename
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            yield path


def create_backup(destination_dir: Path, dry_run: bool = False) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = destination_dir / f"delegation-bot-{timestamp}.zip"
    if dry_run:
        return backup_path

    destination_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in iter_backup_files(ROOT):
            archive.write(path, path.relative_to(ROOT))
    return backup_path


def main(argv: T.Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination",
        default=str(DEFAULT_BACKUP_DIR),
        help="Directory where the backup zip should be written.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the target path without writing.")
    args = parser.parse_args(argv)

    backup_path = create_backup(Path(args.destination), dry_run=args.dry_run)
    action = "Would create" if args.dry_run else "Created"
    print(f"{action} backup: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
