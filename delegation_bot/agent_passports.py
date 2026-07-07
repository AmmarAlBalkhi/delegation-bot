#!/usr/bin/env python3
"""Agent Passport registry helpers for Bring Your Own Agent support."""

from __future__ import annotations

import json
import typing as T
from dataclasses import dataclass, field, replace
from pathlib import Path

from delegation_bot.harness_manifest import Manifest


JsonMap = dict[str, T.Any]
AGENT_REGISTRY_VERSION = "delegation.agent-registry/v1"


@dataclass(frozen=True)
class AgentPassport:
    id: str
    name: str
    source: str
    runtime_type: str
    autonomy_level: str
    risk_level: str
    endpoint: JsonMap
    model: str | None = None
    capability_packs: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    allowed_data: tuple[str, ...] = ()
    required_approvals: tuple[str, ...] = ()
    expected_outputs: tuple[str, ...] = ()
    evidence_requirements: tuple[str, ...] = ()
    promotion_evals: tuple[str, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> JsonMap:
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "runtime_type": self.runtime_type,
            "model": self.model,
            "autonomy_level": self.autonomy_level,
            "risk_level": self.risk_level,
            "endpoint": self.endpoint,
            "capability_packs": list(self.capability_packs),
            "capabilities": list(self.capabilities),
            "allowed_tools": list(self.allowed_tools),
            "allowed_data": list(self.allowed_data),
            "required_approvals": list(self.required_approvals),
            "expected_outputs": list(self.expected_outputs),
            "evidence_requirements": list(self.evidence_requirements),
            "promotion_evals": list(self.promotion_evals),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class AgentPassportReport:
    status: str
    sources: tuple[str, ...]
    passports: tuple[AgentPassport, ...]
    warnings: tuple[str, ...] = ()

    @property
    def passport_count(self) -> int:
        return len(self.passports)

    def to_dict(self) -> JsonMap:
        return {
            "status": self.status,
            "source_count": len(self.sources),
            "sources": list(self.sources),
            "passport_count": self.passport_count,
            "passports": [passport.to_dict() for passport in self.passports],
            "warnings": list(self.warnings),
            "next_actions": list(self.next_actions),
        }

    @property
    def next_actions(self) -> tuple[str, ...]:
        if not self.passports:
            return (
                "Add `agents:` to a Harnessfile, or register custom agents with `--registry examples/agent-passports.yaml`.",
            )
        actions = [
            "Run `delegation plan ... --ledger ...` to produce agent passport ledger evidence.",
            "Run `delegation promote ... --ledger ...` after eval evidence exists.",
        ]
        if self.warnings or any(passport.warnings for passport in self.passports):
            actions.insert(0, "Fix passport warnings before raising autonomy.")
        return tuple(actions)


def build_agent_passport_report(
    *,
    manifest: Manifest | None = None,
    manifest_source: str | None = None,
    registry_paths: T.Sequence[Path] = (),
) -> AgentPassportReport:
    warnings: list[str] = []
    sources: list[str] = []
    passports: list[AgentPassport] = []

    if manifest is not None:
        sources.append(manifest_source or "<harnessfile>")
        passports.extend(_passports_from_manifest(manifest, source=manifest_source or "<harnessfile>"))

    for path in registry_paths:
        source = str(path)
        sources.append(source)
        try:
            registry = _load_registry(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            warnings.append(f"{source}: {exc}")
            continue
        registry_version = registry.get("version")
        if registry_version != AGENT_REGISTRY_VERSION:
            warnings.append(f"{source}: `version` should be {AGENT_REGISTRY_VERSION}")
        passports.extend(_passports_from_registry(registry, source=source, warnings=warnings))

    passports, duplicate_warnings = _dedupe_passports(passports)
    warnings.extend(duplicate_warnings)
    status = "empty" if not passports else "warning" if warnings or any(item.warnings for item in passports) else "ready"
    return AgentPassportReport(
        status=status,
        sources=tuple(_dedupe(sources)),
        passports=tuple(sorted(passports, key=lambda item: (item.source, item.id))),
        warnings=tuple(warnings),
    )


def render_agent_passport_report(report: AgentPassportReport) -> str:
    lines = [
        "Agent Passport Registry",
        "",
        f"Status: {report.status}",
        f"Sources: {len(report.sources)}",
        f"Passports: {report.passport_count}",
    ]
    if report.sources:
        lines.extend(["", "Sources:"])
        lines.extend(f"- {source}" for source in report.sources)

    lines.extend(["", "Passports:"])
    if not report.passports:
        lines.append("- none")
    for passport in report.passports:
        lines.append(f"- {passport.id}: {passport.name}")
        lines.append(
            f"  runtime: {passport.runtime_type}; autonomy: {passport.autonomy_level}; risk: {passport.risk_level}"
        )
        if passport.model:
            lines.append(f"  model: {passport.model}")
        if passport.capabilities:
            lines.append(f"  capabilities: {', '.join(passport.capabilities)}")
        if passport.allowed_tools:
            lines.append(f"  allowed tools: {', '.join(passport.allowed_tools)}")
        if passport.allowed_data:
            lines.append(f"  allowed data: {', '.join(passport.allowed_data)}")
        if passport.required_approvals:
            lines.append(f"  approvals: {', '.join(passport.required_approvals)}")
        if passport.evidence_requirements:
            lines.append(f"  evidence: {', '.join(passport.evidence_requirements)}")
        if passport.promotion_evals:
            lines.append(f"  promotion evals: {', '.join(passport.promotion_evals)}")
        if passport.warnings:
            lines.extend(f"  warning: {warning}" for warning in passport.warnings)

    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)

    lines.extend(["", "Next:"])
    lines.extend(f"- {action}" for action in report.next_actions)
    return "\n".join(lines)


def _passports_from_manifest(manifest: Manifest, *, source: str) -> list[AgentPassport]:
    packs = _capability_pack_map(manifest)
    global_approvals = _global_required_approvals(manifest)
    outputs = _output_types(manifest)
    allowed_tools = _manifest_allowed_tools(manifest)
    allowed_data = _manifest_allowed_data(manifest)

    passports: list[AgentPassport] = []
    agents = manifest.get("agents") if isinstance(manifest.get("agents"), list) else []
    for index, item in enumerate(agents):
        if not isinstance(item, dict):
            continue
        agent_id = _string(item.get("id"), default=f"agent-{index + 1}")
        autonomy = _string(item.get("autonomy_level"), default="suggest")
        pack_ids = tuple(_string_list(item.get("capability_packs")))
        capabilities: list[str] = []
        approvals: list[str] = list(global_approvals)
        warnings: list[str] = []
        for pack_id in pack_ids:
            pack = packs.get(pack_id)
            if not pack:
                warnings.append(f"Unknown capability pack `{pack_id}`.")
                continue
            capabilities.extend(_string_list(pack.get("capabilities")))
            approvals.extend(_string_list(pack.get("approval_required_for")))

        promotion = item.get("promotion") if isinstance(item.get("promotion"), dict) else {}
        promotion_evals = tuple(_string_list(promotion.get("requires_evals")))
        evidence = ["run_ledger", "adapter_result"]
        if promotion_evals:
            evidence.append("eval_report")
        passports.append(
            _with_safety_warnings(
                AgentPassport(
                    id=agent_id,
                    name=_string(item.get("name"), default=agent_id),
                    source=source,
                    runtime_type=_string(item.get("runtime"), default="unknown"),
                    model=_optional_string(item.get("model")),
                    autonomy_level=autonomy,
                    risk_level=_risk_for_autonomy(autonomy),
                    endpoint={"type": "harnessfile.agent", "value": agent_id},
                    capability_packs=pack_ids,
                    capabilities=tuple(_dedupe(capabilities)),
                    allowed_tools=allowed_tools,
                    allowed_data=allowed_data,
                    required_approvals=tuple(_dedupe(approvals)),
                    expected_outputs=outputs,
                    evidence_requirements=tuple(_dedupe(evidence)),
                    promotion_evals=promotion_evals,
                    warnings=tuple(warnings),
                )
            )
        )
    return passports


def _passports_from_registry(registry: JsonMap, *, source: str, warnings: list[str]) -> list[AgentPassport]:
    agents = registry.get("agents")
    if not isinstance(agents, list):
        warnings.append(f"{source}: `agents` must be a list")
        return []
    passports: list[AgentPassport] = []
    for index, item in enumerate(agents):
        if not isinstance(item, dict):
            warnings.append(f"{source}: agents[{index}] must be an object")
            continue
        agent_id = _string(item.get("id"))
        runtime = _string(item.get("runtime_type") or item.get("runtime"))
        if not agent_id or not runtime:
            warnings.append(f"{source}: agents[{index}] needs `id` and `runtime_type`")
            continue
        endpoint = item.get("endpoint") if isinstance(item.get("endpoint"), dict) else {}
        if not endpoint and isinstance(item.get("command"), str):
            endpoint = {"type": "command", "value": item["command"]}
        if not endpoint and isinstance(item.get("api_url"), str):
            endpoint = {"type": "api", "value": item["api_url"]}
        if not endpoint:
            endpoint = {"type": "unspecified", "value": ""}
        autonomy = _string(item.get("autonomy_level"), default="draft")
        passports.append(
            _with_safety_warnings(
                AgentPassport(
                    id=agent_id,
                    name=_string(item.get("name"), default=agent_id),
                    source=source,
                    runtime_type=runtime,
                    model=_optional_string(item.get("model")),
                    autonomy_level=autonomy,
                    risk_level=_string(item.get("risk_level"), default=_risk_for_autonomy(autonomy)),
                    endpoint=endpoint,
                    capability_packs=tuple(_string_list(item.get("capability_packs"))),
                    capabilities=tuple(_string_list(item.get("capabilities"))),
                    allowed_tools=tuple(_string_list(item.get("allowed_tools"))),
                    allowed_data=tuple(_string_list(item.get("allowed_data"))),
                    required_approvals=tuple(_string_list(item.get("required_approvals"))),
                    expected_outputs=tuple(_string_list(item.get("expected_outputs"))),
                    evidence_requirements=tuple(_string_list(item.get("evidence_requirements"))),
                    promotion_evals=tuple(_string_list(item.get("promotion_evals"))),
                )
            )
        )
    return passports


def _with_safety_warnings(passport: AgentPassport) -> AgentPassport:
    warnings = list(passport.warnings)
    if passport.risk_level in {"high", "critical"} and not passport.required_approvals:
        warnings.append("High-risk passport has no required approvals.")
    if not passport.evidence_requirements:
        warnings.append("Passport has no evidence requirements.")
    if not passport.capabilities:
        warnings.append("Passport declares no capabilities.")
    if not passport.allowed_data:
        warnings.append("Passport declares no allowed data scope.")
    return replace(passport, warnings=tuple(_dedupe(warnings)))


def _load_registry(path: Path) -> JsonMap:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ValueError("PyYAML is required to read YAML agent registries") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("Agent registry root must be an object")
    return data


def _capability_pack_map(manifest: Manifest) -> dict[str, JsonMap]:
    packs = manifest.get("capability_packs") if isinstance(manifest.get("capability_packs"), list) else []
    result: dict[str, JsonMap] = {}
    for pack in packs:
        if isinstance(pack, dict) and isinstance(pack.get("id"), str):
            result[pack["id"]] = pack
    return result


def _global_required_approvals(manifest: Manifest) -> tuple[str, ...]:
    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
    approvals = policies.get("approvals") if isinstance(policies.get("approvals"), dict) else {}
    return tuple(_string_list(approvals.get("required_for")))


def _manifest_allowed_tools(manifest: Manifest) -> tuple[str, ...]:
    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
    permissions = policies.get("permissions") if isinstance(policies.get("permissions"), dict) else {}
    return tuple(_string_list(permissions.get("allowed_mcp_tools")))


def _manifest_allowed_data(manifest: Manifest) -> tuple[str, ...]:
    data: list[str] = []
    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
    permissions = policies.get("permissions") if isinstance(policies.get("permissions"), dict) else {}
    data.extend(_string_list(permissions.get("allowed_repositories")))
    context = manifest.get("context") if isinstance(manifest.get("context"), dict) else {}
    sources = context.get("sources") if isinstance(context.get("sources"), list) else []
    for source in sources:
        if isinstance(source, dict) and isinstance(source.get("id"), str):
            data.append(source["id"])
    return tuple(_dedupe(data))


def _output_types(manifest: Manifest) -> tuple[str, ...]:
    outputs = manifest.get("outputs") if isinstance(manifest.get("outputs"), list) else []
    result: list[str] = []
    for output in outputs:
        if isinstance(output, str):
            result.append(output)
        elif isinstance(output, dict) and isinstance(output.get("type"), str):
            result.append(output["type"])
    return tuple(_dedupe(result))


def _risk_for_autonomy(autonomy_level: str) -> str:
    return {
        "suggest": "low",
        "draft": "medium",
        "act": "medium",
        "operate": "high",
        "deploy": "critical",
    }.get(autonomy_level, "medium")


def _dedupe(values: T.Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dedupe_passports(passports: T.Sequence[AgentPassport]) -> tuple[list[AgentPassport], list[str]]:
    seen: set[str] = set()
    result: list[AgentPassport] = []
    warnings: list[str] = []
    for passport in passports:
        if passport.id in seen:
            warnings.append(f"Duplicate agent passport id `{passport.id}` skipped.")
            continue
        seen.add(passport.id)
        result.append(passport)
    return result, warnings


def _string_list(value: T.Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _string(value: T.Any, *, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def _optional_string(value: T.Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
