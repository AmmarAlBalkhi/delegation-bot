from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from delegation_bot.cli import main
from delegation_bot.github_app_plan import build_github_app_plan, render_github_app_plan


class GitHubAppPlanTests(unittest.TestCase):
    def test_read_only_plan_uses_read_permissions(self) -> None:
        plan = build_github_app_plan("read-only", repository="AmmarAlBalkhi/delegation-bot")
        permissions = {permission.name: permission.access for permission in plan.permissions}

        self.assertEqual(permissions["issues"], "read")
        self.assertEqual(permissions["actions"], "read")
        self.assertEqual(plan.token_request["repositories"], ["AmmarAlBalkhi/delegation-bot"])
        self.assertNotIn("metadata", plan.token_request["permissions"])

    def test_issue_write_plan_limits_write_to_issues(self) -> None:
        plan = build_github_app_plan("issue-write")
        permissions = {permission.name: permission.access for permission in plan.permissions}

        self.assertEqual(permissions["issues"], "write")
        self.assertEqual(permissions["actions"], "read")
        self.assertIn("LIVE_GITHUB_ISSUES", " ".join(plan.next_steps))

    def test_actions_control_plan_limits_write_to_actions(self) -> None:
        plan = build_github_app_plan("actions-control")
        permissions = {permission.name: permission.access for permission in plan.permissions}
        rendered = render_github_app_plan(plan)

        self.assertEqual(permissions["actions"], "write")
        self.assertEqual(permissions["issues"], "read")
        self.assertIn("ledger idempotency", rendered)

    def test_cli_writes_github_app_plan_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "github-app-plan.json"
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "github-app-plan",
                        "--mode",
                        "issue-write",
                        "--repository",
                        "AmmarAlBalkhi/delegation-bot",
                        "--output",
                        str(output_path),
                    ]
                )
            data = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(status, 0)
        self.assertEqual(data["mode"], "issue-write")
        self.assertIn("Plan written", output.getvalue())


if __name__ == "__main__":
    unittest.main()
