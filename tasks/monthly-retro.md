---
id: monthly-retro
repository: AmmarAlBalkhi/delegation-bot
title: "Monthly Retrospective"
assign: AmmarAlBalkhi
labels: [recurring, monthly]

date_active: 2025-11-01
due_date:   2025-11-07
interval:   monthly

project:
  owner: AmmarAlBalkhi
  title: Delegation Bot - PoC

# Each subtask has ITS OWN interval
subtasks:
  - id: metrics
    title: "Collect metrics (issues closed, PRs merged, lead time)"
    interval: weekly        # one child per week inside the monthly parent
    window: within_parent

  - id: diary
    title: "Brief daily diary (1–2 bullets)"
    interval: daily         # one child per day inside the monthly parent
    window: within_parent

  - id: summary
    title: "Write monthly summary + next month’s top 3 goals"
    interval: once          # only one child for the month (default if omitted)
---

A monthly parent that spawns weekly/daily/once children within the same month.
