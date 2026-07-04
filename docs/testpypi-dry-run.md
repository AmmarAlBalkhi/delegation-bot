# TestPyPI Dry-Run Notes

This project is not ready for a public PyPI release yet. The safe release path
is to rehearse packaging on TestPyPI first.

Simple version:

```text
Build package.
Inspect files.
Upload to TestPyPI.
Install from TestPyPI in a clean environment.
Run delegation doctor and a dry-run plan.
Only then consider real PyPI.
```

## Preconditions

Before a TestPyPI smoke release:

- `python scripts/qa.py` passes
- `CHANGELOG.md` has a clear unreleased entry
- `LICENSE`, `NOTICE`, and `pyproject.toml` agree
- README examples work from a source install
- no live writes are enabled by default
- no secrets or local paths are included in the source distribution

## Build Locally

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

Inspect what would ship:

```bash
python -m tarfile -l dist/delegation_bot-*.tar.gz
```

## Upload To TestPyPI

Use a TestPyPI token, not a production PyPI token.

```bash
python -m twine upload --repository testpypi dist/*
```

## Smoke Install

In a clean environment:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ delegation-bot
delegation --help
delegation doctor --skip-github
```

Then run a dry-run loop from a local checkout:

```bash
delegation plan examples/ai-harness-control-plane.yaml --ledger .delegation/testpypi-smoke.jsonl
delegation otel .delegation/testpypi-smoke.jsonl --output .delegation/testpypi-smoke-otel.json
delegation apply-issues examples/ai-harness-control-plane.yaml --ledger .delegation/testpypi-smoke.jsonl
```

The last command must stay in preview mode unless the user explicitly passes
the live apply flags.

## Do Not Ship Yet If

- the install command needs undocumented setup
- `delegation doctor --skip-github` fails
- README examples require repository-only imports
- live writes happen without explicit confirmation
- the package includes local caches, backups, secrets, or generated junk
