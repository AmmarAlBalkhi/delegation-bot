#!/usr/bin/env python3
"""Validate playbook catalog metadata."""

from __future__ import annotations

import json
import typing as T
from dataclasses import dataclass, field
from pathlib import Path

from delegation_bot.harness_manifest import load_manifest, validate_manifest


CATALOG_VERSION = "delegation.ai/playbook-catalog/v1"
VALID_EVAL_STATES = {"passed", "blocked", "failed", "skipped"}
JsonMap = dict[str, T.Any]


class PlaybookCatalogError(ValueError):
    """Raised when a playbook catalog cannot be loaded."""


@dataclass(frozen=True)
class CatalogFilter:
    tags: tuple[str, ...] = field(default_factory=tuple)
    adapters: tuple[str, ...] = field(default_factory=tuple)

    def is_active(self) -> bool:
        return bool(self.tags or self.adapters)

    def to_dict(self) -> JsonMap:
        return {
            "tags": list(self.tags),
            "adapters": list(self.adapters),
        }


def load_catalog(path: Path) -> JsonMap:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise PlaybookCatalogError("PyYAML is required to read playbook catalogs") from exc
        data = yaml.safe_load(text)

    if not isinstance(data, dict):
        raise PlaybookCatalogError("Catalog root must be an object")
    return data


def _as_list(value: T.Any) -> list[T.Any]:
    return value if isinstance(value, list) else []


def _executor_adapters(manifest: JsonMap) -> set[str]:
    adapters: set[str] = set()
    for executor in _as_list(manifest.get("executors")):
        if isinstance(executor, dict) and isinstance(executor.get("adapter"), str):
            adapters.add(executor["adapter"])
    return adapters


def _declared_eval_ids(manifest: JsonMap) -> set[str]:
    ids = {"ledger_is_valid"}
    for eval_cfg in _as_list(manifest.get("evals")):
        if isinstance(eval_cfg, dict) and isinstance(eval_cfg.get("id"), str):
            ids.add(eval_cfg["id"])
    return ids


def _normalize_filter_values(values: T.Iterable[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    normalized: list[str] = []
    for value in values:
        clean = value.strip().lower()
        if clean and clean not in normalized:
            normalized.append(clean)
    return tuple(normalized)


def _entry_values(entry: JsonMap, field_name: str) -> set[str]:
    return {
        str(item).strip().lower()
        for item in _as_list(entry.get(field_name))
        if isinstance(item, str) and item.strip()
    }


def filter_catalog(
    catalog: JsonMap,
    *,
    tags: T.Iterable[str] | None = None,
    adapters: T.Iterable[str] | None = None,
) -> tuple[JsonMap, CatalogFilter]:
    catalog_filter = CatalogFilter(
        tags=_normalize_filter_values(tags),
        adapters=_normalize_filter_values(adapters),
    )
    if not catalog_filter.is_active():
        return dict(catalog), catalog_filter

    filtered = dict(catalog)
    playbooks: list[JsonMap] = []
    for entry in _as_list(catalog.get("playbooks")):
        if not isinstance(entry, dict):
            continue
        entry_tags = _entry_values(entry, "tags")
        entry_adapters = _entry_values(entry, "required_adapters")
        if all(tag in entry_tags for tag in catalog_filter.tags) and all(
            adapter in entry_adapters for adapter in catalog_filter.adapters
        ):
            playbooks.append(entry)
    filtered["playbooks"] = playbooks
    filtered["filters"] = catalog_filter.to_dict()
    filtered["filtered_count"] = len(playbooks)
    return filtered, catalog_filter


def catalog_facets(catalog: JsonMap) -> JsonMap:
    tags: set[str] = set()
    adapters: set[str] = set()
    for entry in _as_list(catalog.get("playbooks")):
        if not isinstance(entry, dict):
            continue
        tags.update(_entry_values(entry, "tags"))
        adapters.update(_entry_values(entry, "required_adapters"))
    return {
        "tags": sorted(tags),
        "adapters": sorted(adapters),
    }


def validate_catalog(catalog: JsonMap, root: Path) -> list[str]:
    errors: list[str] = []

    if catalog.get("version") != CATALOG_VERSION:
        errors.append(f"`version` must be {CATALOG_VERSION}")

    playbooks = catalog.get("playbooks")
    if not isinstance(playbooks, list) or not playbooks:
        errors.append("`playbooks` must be a non-empty list")
        return errors

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, entry in enumerate(playbooks):
        if not isinstance(entry, dict):
            errors.append(f"`playbooks[{index}]` must be an object")
            continue

        playbook_id = entry.get("id")
        path_value = entry.get("path")
        if not isinstance(playbook_id, str) or not playbook_id.strip():
            errors.append(f"`playbooks[{index}].id` must be a non-empty string")
            continue
        if playbook_id in seen_ids:
            errors.append(f"duplicate playbook id `{playbook_id}`")
        seen_ids.add(playbook_id)

        if not isinstance(path_value, str) or not path_value.strip():
            errors.append(f"`playbooks[{index}].path` must be a non-empty string")
            continue
        if path_value in seen_paths:
            errors.append(f"duplicate playbook path `{path_value}`")
        seen_paths.add(path_value)

        path = root / path_value
        if not path.exists():
            errors.append(f"`playbooks[{index}].path` does not exist: {path_value}")
            continue

        manifest = load_manifest(path)
        manifest_errors = validate_manifest(manifest)
        if manifest_errors:
            errors.extend(f"{path_value}: {error}" for error in manifest_errors)
            continue
        if manifest.get("id") != playbook_id:
            errors.append(f"`{path_value}` id `{manifest.get('id')}` does not match catalog id `{playbook_id}`")

        tags = entry.get("tags")
        if not isinstance(tags, list) or not tags or not all(isinstance(tag, str) and tag.strip() for tag in tags):
            errors.append(f"`playbooks[{index}].tags` must be a non-empty list of strings")

        required_adapters = entry.get("required_adapters")
        if not isinstance(required_adapters, list) or not required_adapters:
            errors.append(f"`playbooks[{index}].required_adapters` must be a non-empty list")
        else:
            declared_adapters = _executor_adapters(manifest)
            missing = sorted(str(adapter) for adapter in required_adapters if adapter not in declared_adapters)
            if missing:
                errors.append(f"`{playbook_id}` catalog adapters not declared by playbook: {', '.join(missing)}")

        expected_eval_states = entry.get("expected_eval_states")
        if not isinstance(expected_eval_states, dict) or not expected_eval_states:
            errors.append(f"`playbooks[{index}].expected_eval_states` must be a non-empty object")
        else:
            declared_eval_ids = _declared_eval_ids(manifest)
            for eval_id, state in expected_eval_states.items():
                if eval_id not in declared_eval_ids:
                    errors.append(f"`{playbook_id}` expected eval `{eval_id}` is not declared")
                if state not in VALID_EVAL_STATES:
                    errors.append(f"`{playbook_id}` eval `{eval_id}` has invalid expected state `{state}`")

    return errors


def summarize_catalog(catalog: JsonMap, catalog_filter: CatalogFilter | None = None) -> str:
    lines = ["Playbook catalog", ""]
    playbooks = [entry for entry in _as_list(catalog.get("playbooks")) if isinstance(entry, dict)]
    if catalog_filter and catalog_filter.is_active():
        filter_parts: list[str] = []
        if catalog_filter.tags:
            filter_parts.append("tags=" + ", ".join(catalog_filter.tags))
        if catalog_filter.adapters:
            filter_parts.append("adapters=" + ", ".join(catalog_filter.adapters))
        lines.append(f"Filters: {'; '.join(filter_parts)}")
        lines.append(f"Matches: {len(playbooks)}")
        lines.append("")
    if not playbooks:
        lines.append("- none")
        return "\n".join(lines)
    for entry in playbooks:
        tags = ", ".join(str(tag) for tag in _as_list(entry.get("tags")))
        adapters = ", ".join(str(adapter) for adapter in _as_list(entry.get("required_adapters")))
        lines.append(f"- {entry.get('id')} ({entry.get('status', 'unknown')})")
        lines.append(f"  tags: {tags}")
        lines.append(f"  adapters: {adapters}")
    return "\n".join(lines)
