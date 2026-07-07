# Windows EXE Packaging And Install

Goal:

```text
Download delegation.exe.
Run delegation demo.
Try the demo without learning Python packaging.
```

The next product step is a local Windows mission cockpit. See
`docs/windows-app-plan.md`. The app plan is inspectable today:

```powershell
delegation app-plan
delegation app-plan --json
delegation app-state --ledger .delegation/demo.jsonl
delegation app-state --ledger .delegation/demo.jsonl --json
delegation agents examples/ai-harness-control-plane.yaml --registry examples/agent-passports.yaml
delegation agent-gate examples/ai-harness-control-plane.yaml implementer --action create_pull_request --target repository --approval pull_request --ledger .delegation/demo.jsonl --write
delegation agent-audit --ledger .delegation/demo.jsonl
```

## Current State

DelegationHQ is a Python CLI package today:

```bash
python -m pip install -e .
delegation --help
delegation demo
```

This is the right foundation. The console command and QA suite should stay
stable before we ship a standalone executable.

## Build Script

The project now has an optional packaging group:

```bash
python -m pip install -e ".[exe]"
```

That installs PyInstaller for local packaging experiments. The Windows build
script is:

```powershell
.\scripts\build-windows-exe.ps1 -Python python -InstallDependencies
```

The script creates:

```text
dist/delegation.exe
dist/SHA256SUMS.txt
dist/artifacts-manifest.json
```

It also runs this safe smoke test unless `-SkipSmoke` is passed:

```powershell
dist\delegation.exe --version
dist\delegation.exe demo --ledger .delegation\exe-smoke.jsonl
dist\delegation.exe init --goal "prepare this repo for safe AI delegation" --output .delegation\exe-Harnessfile.yaml --force
dist\delegation.exe validate .delegation\exe-Harnessfile.yaml
dist\delegation.exe app-plan
dist\delegation.exe app-state --ledger .delegation\exe-smoke.jsonl
dist\delegation.exe agents examples\ai-harness-control-plane.yaml --registry examples\agent-passports.yaml
dist\delegation.exe agent-gate examples\ai-harness-control-plane.yaml implementer --action create_pull_request --target repository --approval pull_request --ledger .delegation\exe-smoke.jsonl --write
dist\delegation.exe agent-audit --ledger .delegation\exe-smoke.jsonl
```

The executable build bundles `examples/`, `playbooks/`, `schemas/`, `LICENSE`,
`NOTICE`, and `README.md` so the demo, catalog, fixture, and doctor paths do
not depend on a full source checkout.

After smoke checks pass, the script runs:

```powershell
python scripts\delegation.py artifacts --dist dist
python scripts\delegation.py artifacts --dist dist --check
```

`SHA256SUMS.txt` gives users a standard checksum file. The structured
`artifacts-manifest.json` records the package version, artifact names, sizes,
and SHA-256 digests for release automation.

## User-Local Install

After building `dist\delegation.exe`, install it into the current user's
profile:

```powershell
.\scripts\install-windows-exe.ps1 -AddToPath
```

One-command local build plus install:

```powershell
.\scripts\install-windows-exe.ps1 -Build -InstallDependencies -AddToPath
```

The installer copies the executable to:

```text
%LOCALAPPDATA%\DelegationHQ\bin\delegation.exe
```

It runs this smoke check unless `-NoSmoke` is passed:

```powershell
delegation.exe --version
delegation.exe doctor --skip-github
```

`-AddToPath` updates the user PATH only, not the machine PATH. Open a new
terminal before running `delegation` from PATH.

## Local Verification

Local build verification on 2026-07-05:

```text
script: .\scripts\build-windows-exe.ps1 -InstallDependencies
python: 3.12.13
platform: Windows 11
artifact: dist\delegation.exe
smoke: demo, init, validate passed
version: delegation.exe --version passed
```

This proves the build path works on a development machine. It is not yet a
public release artifact; publishing still needs a clean release host, tag, and
checksums.

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
- `.\scripts\build-windows-exe.ps1 -InstallDependencies` passes on Windows
- `.\scripts\install-windows-exe.ps1 -AddToPath` passes on Windows
- the artifact is built from a tagged commit
- docs explain that live writes remain gated
- `delegation.exe --version` matches `pyproject.toml`
- `delegation artifacts --dist dist --check` passes
- checksums and `artifacts-manifest.json` are published next to the artifact

## Sources Checked

Source check date: 2026-07-05.

- [PyInstaller usage documentation](https://pyinstaller.org/en/stable/usage.html)
- [Python zipapp documentation](https://docs.python.org/3/library/zipapp.html)
