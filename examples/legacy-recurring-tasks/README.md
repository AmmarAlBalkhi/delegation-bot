# Legacy Recurring Task Examples

These files are retained from the original Delegation Bot proof of concept.

They show the old rule-based GitHub Issue bot format:

```text
Markdown task spec -> schedule rule -> GitHub Issue
```

The main product direction is now the Harnessfile control plane:

```text
Harnessfile -> dry-run plan -> policy gates -> adapter actions -> run ledger -> evals -> promotion
```

Keep these examples for migration, regression tests, and historical reference.
New users should start with `examples/ai-harness-control-plane.yaml` or the
playbooks in `playbooks/`.

To run these examples with the legacy script, set `TASK_GLOB`:

```bash
TASK_GLOB=examples/legacy-recurring-tasks/*.md \
GITHUB_TOKEN=ghp_your_token \
REPO=owner/repo \
python scripts/delegation_bot.py
```

The legacy script still defaults to `tasks/*.md` for existing users who already
have private task specs in that path.
