# Release And Packaging Plan

DelegationHQ should be easy to try, safe to inspect, and predictable to install.

The public package goal is:

```bash
pip install delegationhq
delegation plan Harnessfile.yaml
```

## Current Status

The repository now has first package metadata in `pyproject.toml`.

Current package facts:

- package name: `delegationhq`
- version: `0.1.0a0`
- current license metadata: `Apache-2.0`
- Python support: `>=3.11`
- console command: `delegation`
- packaging style: setuptools with modern `pyproject.toml`
- optional EXE packaging tools: `python -m pip install -e ".[exe]"`
- Windows EXE build script: `.\scripts\build-windows-exe.ps1`
- Windows EXE user-local installer: `.\scripts\install-windows-exe.ps1`
- import namespace: `delegation_bot`

The code is still alpha. The package metadata exists so contributors and early
users can install from source before a PyPI release.

## Local Install From Source

From the repository root:

```bash
python -m pip install -e .
delegation --version
delegation --help
delegation demo
delegation init --goal "prepare this repo for safe AI delegation" --output Harnessfile.yaml
python -m delegation_bot adapters codex.thread
```

## Local Release Check

Before publishing anything, run the local release-readiness report:

```bash
delegation release-check
```

The command checks package metadata, legal files, release-facing docs,
changelog coverage, CI release evidence, package smoke coverage, Windows EXE
packaging coverage, git cleanliness, and local release artifacts.

It is a dry run. It does not tag, upload, publish, or call external services.
Warnings are allowed during normal development; failed checks must be fixed
before a public release.

For final release rehearsal, require standalone artifacts too:

```bash
delegation release-check --strict-artifacts
```

## Release Checklist

Before a public package release:

- run `delegation release-check`
- run `python scripts/qa.py`
- run `python scripts/package_smoke.py`
- run `delegation release-check --strict-artifacts` after building standalone
  artifacts
- run a source install smoke test
- confirm `delegation --version` matches `pyproject.toml`
- confirm `delegation --help` works after install
- confirm `delegation demo` works outside the source checkout
- confirm README examples use the package command where appropriate
- confirm `LICENSE`, `NOTICE`, and `pyproject.toml` agree
- confirm GitHub Actions uploads ledgers, generated adapter fixtures, QA logs,
  and release metadata
- confirm `.\scripts\build-windows-exe.ps1 -InstallDependencies` passes on
  Windows before publishing any standalone executable
- confirm `CHANGELOG.md` has a release entry
- rehearse the package on TestPyPI
- create a git tag
- publish to TestPyPI before PyPI

See `docs/testpypi-dry-run.md` for the rehearsal commands and smoke checks.
See `docs/windows-exe.md` for the future standalone Windows executable path.
See `docs/brand-transition.md` for package, CLI, and namespace naming rules.

## Package Boundaries

The package exposes the `delegation` CLI and the `delegation_bot.*` Python
namespace. The older `scripts/*.py` files are compatibility wrappers for local
development, existing docs, and older automation.

`delegation_bot` remains the Python import namespace during the compatibility
window. Renaming it would add churn without helping users; the package and
public brand can move to `delegationhq` first.

Before `1.0`, public Python APIs should be named intentionally. Until then, the
CLI and JSON schemas are more stable than the internal module layout.

## Release Philosophy

Public releases should earn trust through restraint:

- no live writes by default
- alpha versions until the Harnessfile and ledger schemas settle
- clear changelog entries
- stable CLI names before marketing
- documented migration notes for breaking schema changes
