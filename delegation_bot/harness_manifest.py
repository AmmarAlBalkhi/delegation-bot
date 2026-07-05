#!/usr/bin/env python3
"""Validate and summarize Delegation AI Harnessfile manifests."""

from __future__ import annotations

import json
import sys
import typing as T
from pathlib import Path


SUPPORTED_VERSION = "delegation.ai/v1"
Manifest = dict[str, T.Any]
ValidationErrors = list[str]
AUTONOMY_LEVELS = {"suggest", "draft", "act", "operate", "deploy"}


class ManifestError(ValueError):
    """Raised when a Harnessfile cannot be loaded or validated."""


def load_manifest(path: Path) -> Manifest:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ManifestError("PyYAML is required to read YAML Harnessfiles") from exc
        data = yaml.safe_load(text)

    if not isinstance(data, dict):
        raise ManifestError("Manifest root must be an object")
    return data


def _require_string(manifest: Manifest, field: str, errors: ValidationErrors) -> None:
    value = manifest.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"`{field}` must be a non-empty string")


def _require_list(manifest: Manifest, field: str, errors: ValidationErrors) -> list[T.Any]:
    value = manifest.get(field)
    if not isinstance(value, list) or not value:
        errors.append(f"`{field}` must be a non-empty list")
        return []
    return value


def _optional_list(manifest: Manifest, field: str, errors: ValidationErrors) -> list[T.Any]:
    value = manifest.get(field, [])
    if value is not None and not isinstance(value, list):
        errors.append(f"`{field}` must be a list when provided")
        return []
    return value if isinstance(value, list) else []


def _validate_optional_string_list(value: T.Any, field_path: str, errors: ValidationErrors) -> None:
    if value is None:
        return
    if not isinstance(value, list):
        errors.append(f"`{field_path}` must be a list when provided")
        return
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"`{field_path}[{index}]` must be a non-empty string")


def validate_manifest(manifest: Manifest) -> ValidationErrors:
    errors: ValidationErrors = []

    if manifest.get("version") != SUPPORTED_VERSION:
        errors.append(f"`version` must be {SUPPORTED_VERSION}")
    _require_string(manifest, "id", errors)
    _require_string(manifest, "objective", errors)

    capability_packs = _optional_list(manifest, "capability_packs", errors)
    capability_pack_ids: set[str] = set()
    for index, capability_pack in enumerate(capability_packs):
        if not isinstance(capability_pack, dict):
            errors.append(f"`capability_packs[{index}]` must be an object")
            continue
        for field in ("id", "description"):
            if not isinstance(capability_pack.get(field), str) or not capability_pack[field].strip():
                errors.append(f"`capability_packs[{index}].{field}` must be a non-empty string")
        capabilities = capability_pack.get("capabilities", [])
        if not isinstance(capabilities, list) or not capabilities:
            errors.append(f"`capability_packs[{index}].capabilities` must be a non-empty list")
        pack_id = capability_pack.get("id")
        if isinstance(pack_id, str):
            if pack_id in capability_pack_ids:
                errors.append(f"duplicate capability pack id `{pack_id}`")
            capability_pack_ids.add(pack_id)

    models = _optional_list(manifest, "models", errors)
    model_ids: set[str] = set()
    for index, model in enumerate(models):
        if not isinstance(model, dict):
            errors.append(f"`models[{index}]` must be an object")
            continue
        for field in ("id", "provider", "model", "role"):
            if not isinstance(model.get(field), str) or not model[field].strip():
                errors.append(f"`models[{index}].{field}` must be a non-empty string")
        model_id = model.get("id")
        if isinstance(model_id, str):
            if model_id in model_ids:
                errors.append(f"duplicate model id `{model_id}`")
            model_ids.add(model_id)

    agents = _optional_list(manifest, "agents", errors)
    for index, agent in enumerate(agents):
        if not isinstance(agent, dict):
            errors.append(f"`agents[{index}]` must be an object")
            continue
        for field in ("id", "runtime", "autonomy_level"):
            if not isinstance(agent.get(field), str) or not agent[field].strip():
                errors.append(f"`agents[{index}].{field}` must be a non-empty string")
        autonomy_level = agent.get("autonomy_level")
        if isinstance(autonomy_level, str) and autonomy_level not in AUTONOMY_LEVELS:
            errors.append(f"`agents[{index}].autonomy_level` must be one of {sorted(AUTONOMY_LEVELS)}")
        agent_pack_refs = agent.get("capability_packs", [])
        if agent_pack_refs is not None and not isinstance(agent_pack_refs, list):
            errors.append(f"`agents[{index}].capability_packs` must be a list when provided")
            agent_pack_refs = []
        for pack_id in agent_pack_refs if isinstance(agent_pack_refs, list) else []:
            if isinstance(pack_id, str) and capability_pack_ids and pack_id not in capability_pack_ids:
                errors.append(f"`agents[{index}].capability_packs` references unknown pack `{pack_id}`")
        model_ref = agent.get("model")
        if isinstance(model_ref, str) and model_ids and model_ref not in model_ids:
            errors.append(f"`agents[{index}].model` references unknown model `{model_ref}`")

    triggers = _require_list(manifest, "triggers", errors)
    for index, trigger in enumerate(triggers):
        if not isinstance(trigger, dict):
            errors.append(f"`triggers[{index}]` must be an object")
        elif not isinstance(trigger.get("type"), str) or not trigger["type"].strip():
            errors.append(f"`triggers[{index}].type` must be a non-empty string")

    executors = _require_list(manifest, "executors", errors)
    executor_ids: set[str] = set()
    for index, executor in enumerate(executors):
        if not isinstance(executor, dict):
            errors.append(f"`executors[{index}]` must be an object")
            continue
        for field in ("id", "kind", "adapter"):
            if not isinstance(executor.get(field), str) or not executor[field].strip():
                errors.append(f"`executors[{index}].{field}` must be a non-empty string")
        executor_id = executor.get("id")
        if isinstance(executor_id, str):
            if executor_id in executor_ids:
                errors.append(f"duplicate executor id `{executor_id}`")
            executor_ids.add(executor_id)
        model_ref = executor.get("model")
        if isinstance(model_ref, str) and model_ids and model_ref not in model_ids:
            errors.append(f"`executors[{index}].model` references unknown model `{model_ref}`")

    outputs = _require_list(manifest, "outputs", errors)
    for index, output in enumerate(outputs):
        if isinstance(output, str) and output.strip():
            continue
        if isinstance(output, dict) and isinstance(output.get("type"), str) and output["type"].strip():
            continue
        errors.append(f"`outputs[{index}]` must be a string or an object with `type`")

    evals = manifest.get("evals", [])
    if evals is not None and not isinstance(evals, list):
        errors.append("`evals` must be a list when provided")
    if isinstance(evals, list):
        for index, item in enumerate(evals):
            if not isinstance(item, dict):
                errors.append(f"`evals[{index}]` must be an object")
                continue
            for field in ("id", "type"):
                if not isinstance(item.get(field), str) or not item[field].strip():
                    errors.append(f"`evals[{index}].{field}` must be a non-empty string")

    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
    permissions = policies.get("permissions") if isinstance(policies.get("permissions"), dict) else {}
    for field in ("allowed_mcp_servers", "allowed_mcp_tools"):
        _validate_optional_string_list(
            permissions.get(field),
            f"policies.permissions.{field}",
            errors,
        )

    return errors


def summarize_manifest(manifest: Manifest) -> str:
    agents = manifest.get("agents") or []
    capability_packs = manifest.get("capability_packs") or []
    models = manifest.get("models") or []
    executors = manifest.get("executors") or []
    outputs = manifest.get("outputs") or []
    evals = manifest.get("evals") or []

    adapters = sorted(
        str(executor.get("adapter"))
        for executor in executors
        if isinstance(executor, dict) and executor.get("adapter")
    )
    output_types: list[T.Any] = [
        output if isinstance(output, str) else output.get("type")
        for output in outputs
        if isinstance(output, (str, dict))
    ]

    lines = [
        f"Harnessfile: {manifest.get('id')}",
        f"Objective: {manifest.get('objective')}",
        f"Agents: {len(agents)}",
        f"Capability packs: {len(capability_packs)}",
        f"Models: {len(models)}",
        f"Executors: {len(executors)} ({', '.join(adapters)})",
        f"Outputs: {', '.join(str(item) for item in output_types)}",
        f"Evals: {len(evals)}",
    ]
    return "\n".join(lines)


def main(argv: T.Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1:
        print("Usage: harness_manifest.py <path>", file=sys.stderr)
        return 2

    path = Path(args[0])
    try:
        manifest = load_manifest(path)
        errors = validate_manifest(manifest)
    except (OSError, json.JSONDecodeError, ManifestError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        print("INVALID Harnessfile", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(summarize_manifest(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
