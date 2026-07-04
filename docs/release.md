# Release And Packaging Plan

Delegation Bot should be easy to try, safe to inspect, and boring to install.

The public package goal is:

```bash
pip install delegation-bot
delegation plan Harnessfile.yaml
```

## Current Status

The repository now has first package metadata in `pyproject.toml`.

Current package facts:

- package name: `delegation-bot`
- version: `0.1.0a0`
- current license metadata: `Apache-2.0`
- Python support: `>=3.11`
- console command: `delegation`
- packaging style: setuptools with modern `pyproject.toml`
- import namespace: `delegation_bot`

The code is still alpha. The package metadata exists so contributors and early
users can install from source before a PyPI release.

## Local Install From Source

From the repository root:

```bash
python -m pip install -e .
delegation --help
delegation plan examples/ai-harness-control-plane.yaml
python -m delegation_bot adapters codex.thread
```

## Release Checklist

Before a public package release:

- run `python scripts/qa.py`
- run a source install smoke test
- confirm `delegation --help` works after install
- confirm README examples use the package command where appropriate
- confirm `LICENSE`, `NOTICE`, and `pyproject.toml` agree
- confirm GitHub Actions uploads ledgers, generated adapter fixtures, QA logs,
  and release metadata
- confirm `CHANGELOG.md` has a release entry
- create a git tag
- publish to TestPyPI before PyPI

## Package Boundaries

The package exposes the `delegation` CLI and the `delegation_bot.*` Python
namespace. The older `scripts/*.py` files are compatibility wrappers for local
development, existing docs, and older automation.

Before `1.0`, public Python APIs should be named intentionally. Until then, the
CLI and JSON schemas are more stable than the internal module layout.

## Release Philosophy

Public releases should earn trust through restraint:

- no live writes by default
- alpha versions until the Harnessfile and ledger schemas settle
- clear changelog entries
- stable CLI names before marketing
- documented migration notes for breaking schema changes
