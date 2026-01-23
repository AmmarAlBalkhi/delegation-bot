# Delegation Bot (GitHub-native, Markdown + YAML)

A lightweight, rule-based “delegation bot” for GitHub repositories: you define tasks as **Markdown files with YAML front-matter**, and a **GitHub Action** turns those task specs into **Issues** (optionally added to a **GitHub Project**) on a schedule or via manual trigger.

The goal is **pre-issue delegation**: expressing *who does what, when, and with what metadata* **before** Issues exist—directly as versioned text in the repo—so task delegation stays transparent, reviewable, and auditable.

---

## What it does

- **Text-native tasks**: tasks live in `tasks/*.md` (YAML header + Markdown body).
- **Recurring tasks**: supports intervals like `daily`, `weekly`, `monthly`, `once`, and `every:N`.
- **Idempotent re-runs**: safe to run repeatedly; the bot avoids duplicates using a hidden fingerprint in the Issue body.
- **Task packs (parent + subtasks)**: a parent Issue can spawn child Issues, keeping a checklist-like structure in GitHub.
- **Optional Project integration (Projects v2)**: created Issues can be auto-added to a Project and fields updated (Status, Due date, etc.).

---

## Quick start (copy/paste setup)

### 1) Add the workflow

Copy `.github/workflows/delegation.yml` into your repo (or keep the one in this repo). The workflow supports:
- manual run (`workflow_dispatch`)
- scheduled runs (`cron`)
- a dry-run vs apply mode via `apply` input

If you use **Projects v2**, create a **fine-grained PAT** and store it as a secret named `PROJECT_TOKEN`.

> GitHub Action triggers (manual + schedule) are documented here: workflow_dispatch and schedule.  
> GitHub docs: `workflow_dispatch` and `schedule` events. 

### 2) Add task files

Create one or more Markdown files in `tasks/` (e.g., `tasks/weekly-status.md`) using YAML front-matter.

### 3) Configure secrets (only if needed)

- `GITHUB_TOKEN` is automatically provided by GitHub Actions (no setup).
- `PROJECT_TOKEN` is **optional** and only required for Projects v2 integration.

> The permission model for `GITHUB_TOKEN` is configurable per workflow/repository; Projects access may require a separate token depending on what you need to do. 

---

## Running the bot

### Manual run (recommended for first test)

1. Go to **Actions → Delegation Bot**
2. Click **Run workflow**
3. Set `apply=false` first (dry-run), then `apply=true` when you’re confident.

### Scheduled run

Edit the cron expression in `.github/workflows/delegation.yml`, e.g.:

```yml
schedule:
  - cron: "0 8 * * *"  # daily at 08:00 UTC
