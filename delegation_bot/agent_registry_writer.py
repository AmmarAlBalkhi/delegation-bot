#!/usr/bin/env python3
"""Write Agent Passport registry entries without hand-editing YAML."""

from __future__ import annotations

import json
import typing as T
from dataclasses import dataclass
from pathlib import Path

from delegation_bot.agent_passports import AGENT_REGISTRY_VERSION, build_agent_passport_report


JsonMap = dict[str, T.Any]
DEFAULT_REGISTRY_PATH = ".delegation/agents.yaml"
DEFAULT_CAPABILITIES = ("read.workspace", "read.run_ledger")
DEFAULT_ALLOWED_DATA = ("workspace", "run_ledger")
DEFAULT_EXPECTED_OUTPUTS = ("summary", "run_ledger")
DEFAULT_EVIDENCE = ("run_ledger", "command_output")


@dataclass(frozen=True)
class AgentAddReport:
    status: str
    registry: str
    agent_id: str
    name: str
    runtime_type: str
    autonomy_level: str
    risk_level: str
    endpoint: JsonMap
    passport_count: int
    replaced: bool = False
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> JsonMap:
        return {
            "status": self.status,
            "registry": self.registry,
            "agent_id": self.agent_id,
            "name": self.name,
            "runtime_type": self.runtime_type,
            "autonomy_level": self.autonomy_level,
            "risk_level": self.risk_level,
            "endpoint": self.endpoint,
            "passport_count": self.passport_count,
            "replaced": self.replaced,
            "warnings": list(self.warnings),
            "next_actions": list(self.next_actions),
        }

    @property
    def next_actions(self) -> tuple[str, ...]:
        return (
            f"delegation agents --registry {self.registry}",
            (
                f"delegation agent-gate --registry {self.registry} {self.agent_id} "
                "--action read.workspace --target workspace"
            ),
            "Give this agent a real mission only after the gate preview is clear.",
        )


def add_agent_to_registry(
    *,
    registry_path: Path,
    agent_id: str,
    name: str | None = None,
    runtime_type: str = "cli.command",
    command: str | None = None,
    api_url: str | None = None,
    webhook_url: str | None = None,
    mcp_endpoint: str | None = None,
    autonomy_level: str = "suggest",
    risk_level: str = "low",
    capabilities: T.Sequence[str] = (),
    allowed_tools: T.Sequence[str] = (),
    allowed_data: T.Sequence[str] = (),
    approvals: T.Sequence[str] = (),
    expected_outputs: T.Sequence[str] = (),
    evidence: T.Sequence[str] = (),
    promotion_evals: T.Sequence[str] = (),
    force: bool = False,
) -> AgentAddReport:
    clean_id = _require_clean("agent_id", agent_id)
    path = registry_path.resolve()
    registry = _load_or_empty_registry(path)
    agents = registry.setdefault("agents", [])
    if not isinstance(agents, list):
        raise ValueError("Agent registry `agents` must be a list")

    existing_index = _find_agent_index(agents, clean_id)
    if existing_index is not None and not force:
        raise ValueError(f"Agent `{clean_id}` already exists. Add --force to replace it.")

    endpoint = _endpoint(command=command, api_url=api_url, webhook_url=webhook_url, mcp_endpoint=mcp_endpoint)
    agent = _agent_entry(
        agent_id=clean_id,
        name=name or clean_id.replace("_", " ").replace("-", " ").title(),
        runtime_type=runtime_type,
        command=command,
        api_url=api_url,
        webhook_url=webhook_url,
        mcp_endpoint=mcp_endpoint,
        endpoint=endpoint,
        autonomy_level=autonomy_level,
        risk_level=risk_level,
        capabilities=capabilities or DEFAULT_CAPABILITIES,
        allowed_tools=allowed_tools,
        allowed_data=allowed_data or DEFAULT_ALLOWED_DATA,
        approvals=approvals,
        expected_outputs=expected_outputs or DEFAULT_EXPECTED_OUTPUTS,
        evidence=evidence or DEFAULT_EVIDENCE,
        promotion_evals=promotion_evals,
    )

    replaced = existing_index is not None
    if existing_index is None:
        agents.append(agent)
    else:
        agents[existing_index] = agent
    _write_registry(path, registry)

    report = build_agent_passport_report(registry_paths=(path,))
    return AgentAddReport(
        status="ready" if report.status != "warning" else "warning",
        registry=str(path),
        agent_id=clean_id,
        name=str(agent["name"]),
        runtime_type=str(agent["runtime_type"]),
        autonomy_level=str(agent["autonomy_level"]),
        risk_level=str(agent["risk_level"]),
        endpoint=endpoint,
        passport_count=report.passport_count,
        replaced=replaced,
        warnings=report.warnings,
    )


def render_agent_add_report(report: AgentAddReport) -> str:
    endpoint_value = str(report.endpoint.get("value") or "not set")
    lines = [
        "Agent Added",
        "",
        f"Status: {report.status}",
        f"Registry: {report.registry}",
        f"Agent: {report.agent_id} ({report.name})",
        f"Runtime: {report.runtime_type}",
        f"Autonomy: {report.autonomy_level}",
        f"Risk: {report.risk_level}",
        f"Endpoint: {report.endpoint.get('type', 'unspecified')} {endpoint_value}",
        f"Passports in registry: {report.passport_count}",
    ]
    if report.replaced:
        lines.append("Replaced: true")
    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend(
        [
            "",
            "Plain language:",
            "- This agent now has an ID card.",
            "- DelegationHQ can gate its actions before it touches useful things.",
            "",
            "Next:",
        ]
    )
    lines.extend(f"- {action}" for action in report.next_actions)
    return "\n".join(lines)


def _agent_entry(
    *,
    agent_id: str,
    name: str,
    runtime_type: str,
    command: str | None,
    api_url: str | None,
    webhook_url: str | None,
    mcp_endpoint: str | None,
    endpoint: JsonMap,
    autonomy_level: str,
    risk_level: str,
    capabilities: T.Sequence[str],
    allowed_tools: T.Sequence[str],
    allowed_data: T.Sequence[str],
    approvals: T.Sequence[str],
    expected_outputs: T.Sequence[str],
    evidence: T.Sequence[str],
    promotion_evals: T.Sequence[str],
) -> JsonMap:
    item: JsonMap = {
        "id": agent_id,
        "name": name,
        "runtime_type": runtime_type,
        "endpoint": endpoint,
        "autonomy_level": autonomy_level,
        "risk_level": risk_level,
        "capabilities": _clean_list(capabilities),
        "allowed_tools": _clean_list(allowed_tools),
        "allowed_data": _clean_list(allowed_data),
        "required_approvals": _clean_list(approvals),
        "expected_outputs": _clean_list(expected_outputs),
        "evidence_requirements": _clean_list(evidence),
        "promotion_evals": _clean_list(promotion_evals),
    }
    if command:
        item["command"] = command.strip()
    if api_url:
        item["api_url"] = api_url.strip()
    if webhook_url:
        item["webhook_url"] = webhook_url.strip()
    if mcp_endpoint:
        item["mcp_endpoint"] = mcp_endpoint.strip()
    return item


def _endpoint(
    *,
    command: str | None,
    api_url: str | None,
    webhook_url: str | None,
    mcp_endpoint: str | None,
) -> JsonMap:
    candidates = [
        ("command", command),
        ("api", api_url),
        ("webhook", webhook_url),
        ("mcp", mcp_endpoint),
    ]
    selected = [(kind, value.strip()) for kind, value in candidates if isinstance(value, str) and value.strip()]
    if len(selected) > 1:
        raise ValueError("Choose only one endpoint: --command, --api-url, --webhook-url, or --mcp-endpoint.")
    if selected:
        kind, value = selected[0]
        return {"type": kind, "value": value}
    return {"type": "unspecified", "value": ""}


def _load_or_empty_registry(path: Path) -> JsonMap:
    if not path.exists():
        return {"version": AGENT_REGISTRY_VERSION, "agents": []}
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ValueError("PyYAML is required to read YAML agent registries") from exc
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Agent registry root must be an object")
    data.setdefault("version", AGENT_REGISTRY_VERSION)
    return data


def _write_registry(path: Path, data: JsonMap) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise ValueError("PyYAML is required to write YAML agent registries") from exc
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=False), encoding="utf-8")


def _find_agent_index(agents: T.Sequence[T.Any], agent_id: str) -> int | None:
    for index, item in enumerate(agents):
        if isinstance(item, dict) and item.get("id") == agent_id:
            return index
    return None


def _require_clean(label: str, value: str) -> str:
    cleaned = value.strip() if isinstance(value, str) else ""
    if not cleaned:
        raise ValueError(f"`{label}` is required")
    return cleaned


def _clean_list(values: T.Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result
