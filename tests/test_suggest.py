from __future__ import annotations

import json
import unittest

from delegation_bot.harness_manifest import validate_manifest
from delegation_bot.harness_plan import build_dry_run_ledger, compile_plan
from delegation_bot.suggest import build_suggestion, infer_template, slugify_goal


class HarnessSuggestionTests(unittest.TestCase):
    def test_slugify_goal_keeps_harness_ids_readable(self) -> None:
        self.assertEqual(
            slugify_goal("Prepare this repo for release!!!"),
            "prepare-this-repo-for-release",
        )

    def test_infer_template_from_goal_keywords(self) -> None:
        template, reason = infer_template("prepare this repo for PyPI release")

        self.assertEqual(template, "release-readiness")
        self.assertIn("release", reason)

    def test_release_suggestion_is_valid_and_compiles_to_ledger(self) -> None:
        suggestion = build_suggestion("prepare this repo for release")
        errors = validate_manifest(suggestion.manifest)

        self.assertEqual(errors, [])
        self.assertEqual(suggestion.template_id, "release-readiness")
        self.assertEqual(suggestion.manifest["metadata"]["suggested_by"], "delegation.suggest")

        plan = compile_plan(suggestion.manifest, source="<test>")
        ledger_events = build_dry_run_ledger(plan)

        self.assertGreater(len(plan.actions), 10)
        self.assertTrue(any(action.adapter == "github.issue" for action in plan.actions))
        self.assertTrue(any(event.type == "plan.compiled" for event in ledger_events))

    def test_code_review_template_declares_claude_model(self) -> None:
        suggestion = build_suggestion("review this pull request")
        models = {model["id"]: model for model in suggestion.manifest["models"]}
        executors = {executor["id"]: executor for executor in suggestion.manifest["executors"]}

        self.assertEqual(suggestion.validate(), [])
        self.assertEqual(suggestion.template_id, "code-review")
        self.assertEqual(models["claude_reviewer_model"]["provider"], "anthropic")
        self.assertEqual(executors["review_agent"]["adapter"], "claude.code")
        self.assertEqual(executors["review_agent"]["model"], "claude_reviewer_model")

    def test_suggestion_manifest_is_json_serializable(self) -> None:
        suggestion = build_suggestion("refresh the README docs")

        encoded = json.dumps(suggestion.manifest, sort_keys=True)

        self.assertIn("documentation-refresh", encoded)


if __name__ == "__main__":
    unittest.main()
