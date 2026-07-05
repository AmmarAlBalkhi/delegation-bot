from __future__ import annotations

import json
import unittest

from delegation_bot.harness_manifest import validate_manifest
from delegation_bot.model_suggest_fixtures import validate_model_suggestion_draft
from delegation_bot.model_suggest_live import (
    ANTHROPIC_MESSAGES_URL,
    OPENAI_RESPONSES_URL,
    LiveModelConfig,
    LiveModelSuggestionError,
    api_key_from_env,
    build_live_model_config,
    fetch_live_model_suggestion,
)
from delegation_bot.suggest import build_suggestion


def _draft_payload(*, provider: str, model: str) -> dict[str, object]:
    suggestion = build_suggestion("prepare this repo for release")
    manifest = dict(suggestion.manifest)
    manifest["metadata"] = {
        **manifest["metadata"],
        "suggested_by": "delegation.suggest.model",
    }
    return {
        "version": "delegation.ai/harness-suggestion-draft/v1",
        "goal": "prepare this repo for release",
        "draft_source": "model",
        "provider": provider,
        "model": model,
        "rationale": "A live model proposed the release-readiness template.",
        "manifest": manifest,
        "safety_notes": ["Dry-run first.", "Human approval remains required."],
        "validation_expectations": ["Harnessfile validates before planning."],
    }


class LiveModelSuggestionTests(unittest.TestCase):
    def test_api_key_from_env_is_provider_specific(self) -> None:
        self.assertEqual(api_key_from_env("openai", {"OPENAI_API_KEY": "sk-test"}), "sk-test")
        self.assertEqual(api_key_from_env("anthropic", {"ANTHROPIC_API_KEY": "claude-test"}), "claude-test")

    def test_live_model_config_uses_current_defaults(self) -> None:
        openai_config = build_live_model_config("openai", environ={"OPENAI_API_KEY": "sk-test"})
        anthropic_config = build_live_model_config("anthropic", environ={"ANTHROPIC_API_KEY": "claude-test"})

        self.assertEqual(openai_config.model, "gpt-5.5")
        self.assertEqual(anthropic_config.model, "claude-sonnet-5")

    def test_missing_api_key_raises_clear_error(self) -> None:
        with self.assertRaises(LiveModelSuggestionError) as context:
            build_live_model_config("openai", environ={})

        self.assertIn("OPENAI_API_KEY", str(context.exception))
        self.assertIn("no-network mode", str(context.exception))

    def test_openai_live_suggestion_uses_responses_endpoint_and_validates(self) -> None:
        payload = _draft_payload(provider="openai", model="gpt-test")
        calls: list[tuple[str, dict[str, str], dict[str, object], int]] = []

        def sender(url: str, headers: dict[str, str], body: dict[str, object], timeout: int) -> dict[str, object]:
            calls.append((url, headers, body, timeout))
            return {"output_text": json.dumps(payload)}

        draft = fetch_live_model_suggestion(
            "prepare this repo for release",
            config=LiveModelConfig(provider="openai", model="gpt-test", api_key="sk-test"),
            sender=sender,
        )

        self.assertEqual(draft.provider, "openai")
        self.assertEqual(validate_manifest(draft.manifest), [])
        self.assertEqual(calls[0][0], OPENAI_RESPONSES_URL)
        self.assertIn("Authorization", calls[0][1])
        self.assertEqual(calls[0][2]["model"], "gpt-test")

    def test_anthropic_live_suggestion_uses_messages_endpoint_and_validates(self) -> None:
        payload = _draft_payload(provider="anthropic", model="claude-test")
        calls: list[tuple[str, dict[str, str], dict[str, object], int]] = []

        def sender(url: str, headers: dict[str, str], body: dict[str, object], timeout: int) -> dict[str, object]:
            calls.append((url, headers, body, timeout))
            return {"content": [{"type": "text", "text": json.dumps(payload)}]}

        draft = fetch_live_model_suggestion(
            "prepare this repo for release",
            config=LiveModelConfig(provider="anthropic", model="claude-test", api_key="claude-test"),
            sender=sender,
        )

        self.assertEqual(draft.provider, "anthropic")
        self.assertEqual(validate_manifest(draft.manifest), [])
        self.assertEqual(calls[0][0], ANTHROPIC_MESSAGES_URL)
        self.assertIn("x-api-key", calls[0][1])
        self.assertEqual(calls[0][2]["model"], "claude-test")

    def test_invalid_model_json_is_rejected(self) -> None:
        def sender(url: str, headers: dict[str, str], body: dict[str, object], timeout: int) -> dict[str, object]:
            return {"output_text": "not json"}

        with self.assertRaises(LiveModelSuggestionError):
            fetch_live_model_suggestion(
                "prepare this repo for release",
                config=LiveModelConfig(provider="openai", model="gpt-test", api_key="sk-test"),
                sender=sender,
            )

    def test_live_model_draft_metadata_is_allowed(self) -> None:
        errors = validate_model_suggestion_draft(_draft_payload(provider="openai", model="gpt-test"))

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
