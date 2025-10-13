---
# Defaults applied to all tasks
repository: ammar-uni/delegation-bot
assign: ammar-uni
labels: [delegation, generated-by-bot]

tasks:
  - id: t1-outline
    title: "Prepare thesis outline"
    date_active: 2025-10-13
    due_date: 2025-10-20
    once: false
    type: issue

  - id: t2-send-expose
    title: "Send exposé email to Prof. Wagner"
    date_active: 2025-10-13
    due_date: 2025-10-15
    labels: delegation        # string form; overrides defaults
    once: true
    type: issue

  - id: t3-future-proof
    title: "Auto-add proof (board screenshot)"
    date_active: 2025-10-20   # FUTURE → will be SKIPPED today (2025-10-13)
    labels: [delegation, generated-by-bot, proof]  # overrides defaults with extra tag
    once: false
    type: issue
---
- [ ] Outline ready (t1)
- [ ] Email sent (t2)
- [ ] Board screenshot collected (t3)
