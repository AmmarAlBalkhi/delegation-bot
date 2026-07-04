from __future__ import annotations

import unittest

from delegation_bot.harness_manifest import validate_manifest
from delegation_bot.harness_plan import build_dry_run_ledger, compile_plan
from delegation_bot.model_suggest_fixtures import (
    ModelSuggestionFixtureError,
    load_model_suggestion_fixture,
    validate_model_suggestion_draft,
)


class ModelSuggestionFixtureTests(unittest.TestCase):
    def test_openai_release_fixture_validates_and_plans(self) -> None:
        draft = load_model_suggestion_fixture("openai", "release-readiness")

        self.assertEqual(draft.provider, "openai")
        self.assertEqual(draft.template_id, "release-readiness")
        self.assertEqual(validate_manifest(draft.manifest), [])

        plan = compile_plan(draft.manifest, source=str(draft.source_path))
        ledger = build_dry_run_ledger(plan)

        self.assertTrue(any(action.adapter == "openai.agents" for action in plan.actions))
        self.assertTrue(any(event.type == "plan.compiled" for event in ledger))

    def test_anthropic_code_review_fixture_validates_and_plans(self) -> None:
        draft = load_model_suggestion_fixture("anthropic", "code-review")
        plan = compile_plan(draft.manifest, source=str(draft.source_path))

        self.assertEqual(draft.provider, "anthropic")
        self.assertEqual(draft.template_id, "code-review")
        self.assertTrue(any(action.adapter == "anthropic.messages" for action in plan.actions))

    def test_invalid_fixture_is_rejected_before_planning(self) -> None:
        errors = validate_model_suggestion_draft(
            {
                "version": "delegation.ai/harness-suggestion-draft/v1",
                "goal": "bad",
                "draft_source": "model",
                "provider": "openai",
                "model": "fixture",
                "rationale": "Bad fixture.",
                "manifest": {},
                "safety_notes": ["no live call"],
                "validation_expectations": ["must fail"],
            }
        )

        self.assertTrue(any(error.startswith("manifest:") for error in errors))

    def test_missing_fixture_raises_clear_error(self) -> None:
        with self.assertRaises(ModelSuggestionFixtureError):
            load_model_suggestion_fixture("openai", "weekly-planning")


if __name__ == "__main__":
    unittest.main()
