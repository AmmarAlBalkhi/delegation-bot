#!/usr/bin/env python3
"""Load no-network model-backed Harnessfile suggestion fixtures."""

from __future__ import annotations

import json
import typing as T
from dataclasses import dataclass, field
from pathlib import Path

from delegation_bot.harness_manifest import Manifest, validate_manifest


JsonMap = dict[str, T.Any]
FIXTURE_VERSION = "delegation.ai/harness-suggestion-draft/v1"
FIXTURE_PROVIDERS = ("openai", "anthropic")
SUPPORTED_PROVIDERS = ("openai", "anthropic", "ollama", "local")
SUPPORTED_SUGGESTED_BY = ("delegation.suggest.model_fixture", "delegation.suggest.model")
DEFAULT_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "examples" / "model-suggestions"


class ModelSuggestionFixtureError(ValueError):
    """Raised when a model-backed suggestion fixture is invalid."""


@dataclass(frozen=True)
class ModelSuggestionDraft:
    goal: str
    provider: str
    model: str
    rationale: str
    manifest: Manifest
    safety_notes: tuple[str, ...]
    validation_expectations: tuple[str, ...]
    source_path: Path | None = None
    raw: JsonMap = field(default_factory=dict)

    @property
    def template_id(self) -> str:
        metadata = self.manifest.get("metadata") if isinstance(self.manifest.get("metadata"), dict) else {}
        value = metadata.get("suggestion_template") if isinstance(metadata, dict) else None
        return value if isinstance(value, str) and value.strip() else f"{self.provider}-fixture"

    def to_dict(self) -> JsonMap:
        return {
            "version": FIXTURE_VERSION,
            "goal": self.goal,
            "draft_source": "model",
            "provider": self.provider,
            "model": self.model,
            "rationale": self.rationale,
            "manifest": self.manifest,
            "safety_notes": list(self.safety_notes),
            "validation_expectations": list(self.validation_expectations),
        }


def fixture_path(provider: str, template_id: str, *, root: Path | None = None) -> Path:
    provider_id = _clean_id(provider)
    template = _clean_id(template_id)
    return (root or DEFAULT_FIXTURE_ROOT) / f"{provider_id}-{template}.json"


def load_model_suggestion_fixture(
    provider: str,
    template_id: str,
    *,
    root: Path | None = None,
) -> ModelSuggestionDraft:
    if provider not in FIXTURE_PROVIDERS:
        raise ModelSuggestionFixtureError(
            f"No no-network fixture provider `{provider}`. Fixture providers: {', '.join(FIXTURE_PROVIDERS)}."
        )
    path = fixture_path(provider, template_id, root=root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ModelSuggestionFixtureError(f"No fixture found for `{provider}` and `{template_id}` at {path}.") from exc
    except json.JSONDecodeError as exc:
        raise ModelSuggestionFixtureError(f"Fixture JSON error: {exc}") from exc
    return parse_model_suggestion_draft(data, source_path=path)


def parse_model_suggestion_draft(data: JsonMap, *, source_path: Path | None = None) -> ModelSuggestionDraft:
    if not isinstance(data, dict):
        raise ModelSuggestionFixtureError("Model suggestion draft must be a JSON object.")
    errors = validate_model_suggestion_draft(data)
    if errors:
        raise ModelSuggestionFixtureError("; ".join(errors))

    return ModelSuggestionDraft(
        goal=str(data["goal"]),
        provider=str(data["provider"]),
        model=str(data["model"]),
        rationale=str(data["rationale"]),
        manifest=T.cast(Manifest, data["manifest"]),
        safety_notes=tuple(str(item) for item in data["safety_notes"]),
        validation_expectations=tuple(str(item) for item in data["validation_expectations"]),
        source_path=source_path,
        raw=data,
    )


def validate_model_suggestion_draft(data: JsonMap) -> list[str]:
    errors: list[str] = []
    required = (
        "version",
        "goal",
        "draft_source",
        "provider",
        "model",
        "rationale",
        "manifest",
        "safety_notes",
        "validation_expectations",
    )
    for field_name in required:
        if field_name not in data:
            errors.append(f"missing `{field_name}`")
    if errors:
        return errors

    if data.get("version") != FIXTURE_VERSION:
        errors.append(f"version must be `{FIXTURE_VERSION}`")
    if data.get("draft_source") != "model":
        errors.append("draft_source must be `model`")
    if data.get("provider") not in SUPPORTED_PROVIDERS:
        errors.append("provider must be one of: " + ", ".join(SUPPORTED_PROVIDERS))
    for field_name in ("goal", "model", "rationale"):
        if not isinstance(data.get(field_name), str) or not str(data.get(field_name)).strip():
            errors.append(f"`{field_name}` must be a non-empty string")
    for field_name in ("safety_notes", "validation_expectations"):
        value = data.get(field_name)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            errors.append(f"`{field_name}` must be a non-empty string list")

    manifest = data.get("manifest")
    if not isinstance(manifest, dict):
        errors.append("`manifest` must be an object")
    else:
        errors.extend(f"manifest: {error}" for error in validate_manifest(T.cast(Manifest, manifest)))
        metadata = manifest.get("metadata") if isinstance(manifest.get("metadata"), dict) else {}
        if metadata.get("suggested_by") not in SUPPORTED_SUGGESTED_BY:
            errors.append(
                "manifest metadata.suggested_by must be one of: " + ", ".join(SUPPORTED_SUGGESTED_BY)
            )
    return errors


def _clean_id(value: str) -> str:
    clean = value.strip().lower().replace("_", "-")
    if not clean:
        raise ModelSuggestionFixtureError("fixture ids must be non-empty")
    return clean
