# Windows EXE Packaging Plan

Goal:

```text
Download delegation.exe.
Run delegation demo.
Try the demo without learning Python packaging.
```

## Current State

Delegation Bot is a Python CLI package today:

```bash
python -m pip install -e .
delegation --help
delegation demo
```

This is the right foundation. The console command and QA suite should stay
stable before we ship a standalone executable.

## Future EXE Path

The project now has an optional packaging group:

```bash
python -m pip install -e ".[exe]"
```

That installs PyInstaller for local packaging experiments. A future Windows
build command should create:

```text
dist/delegation.exe
```

Expected smoke test:

```powershell
dist\delegation.exe demo --ledger .delegation\exe-smoke.jsonl
dist\delegation.exe init --goal "prepare this repo for safe AI delegation" --output Harnessfile.yaml
dist\delegation.exe validate Harnessfile.yaml
```

## Why PyInstaller

PyInstaller bundles a Python application and its dependencies so users can run
it without installing Python modules separately. That is the right target for a
friendly Windows `.exe`.

## Zipapp Option

Python's standard `zipapp` can create executable Python archives. It is useful
for a lightweight `.pyz`, but users still need a Python interpreter. So zipapp
can be an intermediate artifact, not the final beginner-friendly Windows path.

## Release Rules

Do not publish an `.exe` until:

- `python scripts/qa.py` passes
- `python scripts/package_smoke.py` passes
- the executable smoke test passes on Windows
- the artifact is built from a tagged commit
- docs explain that live writes remain gated
- the executable version matches `pyproject.toml`
- checksums are published next to the artifact

## Sources Checked

Source check date: 2026-07-05.

- [PyInstaller documentation](https://pyinstaller.org/)
- [Python zipapp documentation](https://docs.python.org/3/library/zipapp.html)
