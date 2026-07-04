# Agent Operating Rules

This repository is becoming a control plane for delegated AI work. Treat it like
infrastructure.

## Before Editing

- Check `git status --short --branch`.
- Create a backup before substantial edits:

  ```bash
  python scripts/backup_repo.py
  ```

- Read the relevant docs before changing architecture:
  - `docs/vision.md`
  - `docs/architecture.md`
  - `docs/qa.md`
  - `docs/decision-log.md`

## While Editing

- Keep changes small, typed, and testable.
- Prefer pure validation and compilation steps before live execution.
- Add or update tests for any behavior change.
- Update docs when adding new manifest fields, policies, adapters, evals, or QA expectations.
- Do not introduce live network, GitHub writes, or agent execution without a dry-run path.

## Required QA

Run this before handing work back:

```bash
python scripts/qa.py
```

If Python dependencies are missing, install `requirements.txt` in the active
environment before judging the result.

## Backup Rhythm

- Backup before a major change.
- Backup after a green QA milestone.
- Keep backups outside the git-tracked repo.

## Completion Standard

Report:

- what changed
- where it changed
- which QA command ran
- where the latest backup lives
- any residual risk or next recommended step
