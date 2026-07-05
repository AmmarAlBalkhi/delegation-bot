#!/usr/bin/env python3
"""Smoke test the installed package from outside the source checkout."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="delegation-package-smoke-") as tmpdir:
        tmp = Path(tmpdir)
        site_dir = tmp / "site"
        install = _run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--quiet",
                "--no-deps",
                "--target",
                str(site_dir),
                str(ROOT),
            ],
            cwd=tmp,
        )
        if install.returncode != 0:
            print("FAIL: package install smoke")
            print(install.stdout)
            print(install.stderr, file=sys.stderr)
            return install.returncode

        env = dict(os.environ)
        env["PYTHONPATH"] = str(site_dir)
        ledger = tmp / "demo.jsonl"
        demo = _run(
            [
                sys.executable,
                "-m",
                "delegation_bot",
                "demo",
                "--ledger",
                str(ledger),
            ],
            cwd=tmp,
            env=env,
        )
        if demo.returncode != 0:
            print("FAIL: installed package demo smoke")
            print(demo.stdout)
            print(demo.stderr, file=sys.stderr)
            return demo.returncode
        if "Status: ready" not in demo.stdout or not ledger.exists():
            print("FAIL: installed package demo smoke did not produce ready output and ledger")
            print(demo.stdout)
            return 1

    print("PASS: installed package demo smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
