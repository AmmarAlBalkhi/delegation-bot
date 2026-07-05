"""Opt-in live model-backed Harnessfile suggestions."""

from __future__ import annotations

import json
import os
import typing as T
from dataclasses import dataclass

from delegation_bot.model_suggest_fixtures import (
    FIXTURE_VERSION,
    JsonMap,
    ModelSuggestionDraft,
    parse_model_suggestion_draft,
)
from delegation_bot.suggest import DEFAULT_OWNER, DEFAULT_REPOSITORY, build_suggestion


LIVE_PROVIDERS = ("openai", "anthropic")
DEFAULT_MODELS = {
    "openai": "gpt-5.5",
    "anthropic": "claude-sonnet-5",
}
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_OUTPUT_TOKENS = 6000
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class LiveModelSuggestionError(ValueError):
    """Raised when a live model suggestion cannot be fetched or trusted."""


@dataclass(frozen=True)
class LiveModelConfig:
    provider: str
    model: str
    api_key: str
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS


Sender = T.Callable[[str, dict[str, str], JsonMap, int], JsonMap]


def api_key_from_env(provider: str, environ: T.Mapping[str, str] | None = None) -> str:
    env = environ or os.environ
    key_names = {
        "openai": ("OPENAI_API_KEY",),
        "anthropic": ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
    }.get(provider)
    if not key_names:
        raise LiveModelSuggestionError(f"Unsupported live model provider `{provider}`.")
    for key_name in key_names:
        value = env.get(key_name)
        if value and value.strip():
            return value.strip()
    raise LiveModelSuggestionError(
        f"{' or '.join(key_names)} is required for live `{provider}` suggestions. "
        "Use --draft-source template or --draft-source fixture for no-network mode."
    )


def build_live_model_config(
    provider: str,
    *,
    model: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    environ: T.Mapping[str, str] | None = None,
) -> LiveModelConfig:
    provider_id = provider.strip().lower()
    if provider_id not in LIVE_PROVIDERS:
        raise LiveModelSuggestionError("provider must be one of: " + ", ".join(LIVE_PROVIDERS))
    if timeout_seconds <= 0:
        raise LiveModelSuggestionError("--timeout-seconds must be greater than 0")
    if max_output_tokens <= 0:
        raise LiveModelSuggestionError("--max-output-tokens must be greater than 0")
    selected_model = (model or DEFAULT_MODELS[provider_id]).strip()
    if not selected_model:
        raise LiveModelSuggestionError("--model must be a non-empty string")
    return LiveModelConfig(
        provider=provider_id,
        model=selected_model,
        api_key=api_key_from_env(provider_id, environ=environ),
        timeout_seconds=timeout_seconds,
        max_output_tokens=max_output_tokens,
    )


def fetch_live_model_suggestion(
    goal: str,
    *,
    config: LiveModelConfig,
    repository: str = DEFAULT_REPOSITORY,
    owner: str = DEFAULT_OWNER,
    template: str | None = None,
    sender: Sender | None = None,
) -> ModelSuggestionDraft:
    if config.provider == "openai":
        data = _call_openai(
            goal,
            config=config,
            repository=repository,
            owner=owner,
            template=template,
            sender=sender or _post_json,
        )
    elif config.provider == "anthropic":
        data = _call_anthropic(
            goal,
            config=config,
            repository=repository,
            owner=owner,
            template=template,
            sender=sender or _post_json,
        )
    else:  # pragma: no cover - guarded by LiveModelConfig
        raise LiveModelSuggestionError(f"Unsupported live model provider `{config.provider}`.")

    draft = parse_model_suggestion_draft(data)
    if draft.provider != config.provider:
        raise LiveModelSuggestionError(
            f"Model draft provider `{draft.provider}` did not match requested provider `{config.provider}`."
        )
    if draft.model != config.model:
        raise LiveModelSuggestionError(f"Model draft must report model `{config.model}`.")
    return draft


def build_prompt_parts(
    goal: str,
    *,
    provider: str,
    model: str,
    repository: str,
    owner: str,
    template: str | None = None,
) -> tuple[str, str]:
    fallback = build_suggestion(goal, repository=repository, owner=owner, template=template)
    reference_manifest = dict(fallback.manifest)
    reference_manifest["metadata"] = {
        **T.cast(dict[str, T.Any], reference_manifest.get("metadata", {})),
        "suggested_by": "delegation.suggest.model",
    }
    system_prompt = "\n".join(
        [
            "You draft Delegation Bot Harnessfiles.",
            "Return only one JSON object. Do not wrap it in Markdown.",
            "The JSON object must match the harness suggestion draft envelope.",
            "Prefer dry-run adapters and explicit human approval for risky actions.",
            "Do not claim execution happened.",
            "Do not mark evals as passed.",
            "Do not include secrets, tokens, private data, or live credentials.",
            "Keep the user experience simple: useful first, details available later.",
        ]
    )
    user_prompt = json.dumps(
        {
            "version": FIXTURE_VERSION,
            "task": "Draft a Delegation Bot Harnessfile suggestion envelope.",
            "goal": goal,
            "provider": provider,
            "model": model,
            "repository": repository,
            "owner": owner,
            "template_hint": template or fallback.template_id,
            "required_output_shape": {
                "version": FIXTURE_VERSION,
                "goal": "string",
                "draft_source": "model",
                "provider": provider,
                "model": model,
                "rationale": "short reason for the proposed Harnessfile",
                "manifest": "valid Delegation Bot Harnessfile object",
                "safety_notes": ["one or more short strings"],
                "validation_expectations": ["one or more short strings"],
            },
            "manifest_rules": [
                "manifest.version must be delegation.ai/v1",
                "manifest.metadata.suggested_by must be delegation.suggest.model",
                "manifest.metadata.trust_boundary must mention AI proposes and Delegation Bot verifies",
                "live writes, workflows, pull requests, agent execution, and deployments need human approval",
                "the manifest must validate before any plan is compiled",
            ],
            "valid_reference_manifest": reference_manifest,
        },
        indent=2,
        sort_keys=True,
    )
    return system_prompt, user_prompt


def _call_openai(
    goal: str,
    *,
    config: LiveModelConfig,
    repository: str,
    owner: str,
    template: str | None,
    sender: Sender,
) -> JsonMap:
    system_prompt, user_prompt = build_prompt_parts(
        goal,
        provider=config.provider,
        model=config.model,
        repository=repository,
        owner=owner,
        template=template,
    )
    response = sender(
        OPENAI_RESPONSES_URL,
        {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        {
            "model": config.model,
            "input": [
                {"role": "developer", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_output_tokens": config.max_output_tokens,
        },
        config.timeout_seconds,
    )
    text = _extract_openai_text(response)
    return _json_from_model_text(text)


def _call_anthropic(
    goal: str,
    *,
    config: LiveModelConfig,
    repository: str,
    owner: str,
    template: str | None,
    sender: Sender,
) -> JsonMap:
    system_prompt, user_prompt = build_prompt_parts(
        goal,
        provider=config.provider,
        model=config.model,
        repository=repository,
        owner=owner,
        template=template,
    )
    response = sender(
        ANTHROPIC_MESSAGES_URL,
        {
            "x-api-key": config.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        },
        {
            "model": config.model,
            "max_tokens": config.max_output_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        config.timeout_seconds,
    )
    structured_input = _extract_anthropic_tool_input(response)
    if structured_input is not None:
        return structured_input
    text = _extract_anthropic_text(response)
    return _json_from_model_text(text)


def _post_json(url: str, headers: dict[str, str], payload: JsonMap, timeout_seconds: int) -> JsonMap:
    requests = _requests_module()
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
        response.raise_for_status()
        data = response.json()
    except requests.HTTPError as exc:
        body = exc.response.text[:500] if exc.response is not None else str(exc)
        raise LiveModelSuggestionError(f"Live model request failed: {body}") from exc
    except requests.RequestException as exc:
        raise LiveModelSuggestionError(f"Live model request failed: {exc}") from exc
    except ValueError as exc:
        raise LiveModelSuggestionError("Live model response was not valid JSON.") from exc
    if not isinstance(data, dict):
        raise LiveModelSuggestionError("Live model response must be a JSON object.")
    return data


def _requests_module() -> T.Any:
    try:
        import requests
    except ImportError as exc:
        raise LiveModelSuggestionError(
            "The `requests` package is required for live model suggestions. "
            "Install dependencies with `python -m pip install -r requirements.txt`, or use "
            "`--draft-source template` / `--draft-source fixture` for no-network mode."
        ) from exc
    return requests


def _extract_openai_text(response: JsonMap) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    parts: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    if parts:
        return "\n".join(parts)
    raise LiveModelSuggestionError("OpenAI response did not include output text.")


def _extract_anthropic_text(response: JsonMap) -> str:
    parts: list[str] = []
    for block in response.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(str(block["text"]))
    if parts:
        return "\n".join(parts)
    raise LiveModelSuggestionError("Anthropic response did not include text content.")


def _extract_anthropic_tool_input(response: JsonMap) -> JsonMap | None:
    for block in response.get("content", []):
        if isinstance(block, dict) and block.get("type") == "tool_use" and isinstance(block.get("input"), dict):
            return T.cast(JsonMap, block["input"])
    return None


def _json_from_model_text(text: str) -> JsonMap:
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.strip("`").strip()
        if clean.lower().startswith("json"):
            clean = clean[4:].strip()
    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        start = clean.find("{")
        end = clean.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise LiveModelSuggestionError("Model did not return a JSON object.")
        try:
            data = json.loads(clean[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LiveModelSuggestionError(f"Model returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LiveModelSuggestionError("Model JSON must be an object.")
    return data
