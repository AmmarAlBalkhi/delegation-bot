# Delegation Bot (Rule-Based, Markdown → GitHub Issues)

A minimal, thesis-friendly bot that scans `tasks/*.md` files containing **YAML front-matter** and creates **GitHub issues**.  
It’s **idempotent** (won’t duplicate issues) and integrates with a **GitHub Project** board for coordination.

---

## Features
- **Markdown + YAML** task files (`tasks/*.md`)
- **Activation date** (`date_active`) to delay creation until a specific day
- **Dry-run vs. apply** toggle via workflow input
- **Idempotency** using a hidden fingerprint embedded in the issue body
- **Project integration** (auto-add new bot issues to your project)
- **Scheduled** daily run via cron (and manual runs anytime)

---

## Folder structure
```text
tasks/               # YAML + Markdown tasks
scripts/             # Bot scripts
.github/workflows/   # GitHub Actions workflow
