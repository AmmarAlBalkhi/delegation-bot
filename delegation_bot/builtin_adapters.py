#!/usr/bin/env python3
"""Built-in dry-run adapter implementations."""

from __future__ import annotations

import hashlib
import json
import re
import typing as T

from delegation_bot.adapter_sdk import (
    Adapter,
    AdapterEvent,
    AdapterRequest,
    ContractBackedDryRunAdapter,
    JsonMap,
)
from delegation_bot.adapters import get_adapter_contract


def _contract_or_raise(adapter_id: str):
    contract = get_adapter_contract(adapter_id)
    if contract is None:
        raise LookupError(f"missing built-in adapter contract `{adapter_id}`")
    return contract


def _string_input(request: AdapterRequest, key: str, default: str = "") -> str:
    value = request.inputs.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else default


def _input_value(request: AdapterRequest, key: str, default: T.Any) -> T.Any:
    value = request.inputs.get(key)
    return default if value is None else value


def _list_input(request: AdapterRequest, key: str) -> list[T.Any]:
    value = request.inputs.get(key)
    return value if isinstance(value, list) else []


def _json_digest(*parts: T.Any, length: int = 16) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length]


def _preview(value: T.Any, limit: int = 240) -> T.Any:
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, (dict, list)):
        text = json.dumps(value, sort_keys=True, default=str)
        return text[:limit]
    return value


ISSUE_MARKER_RE = re.compile(r"delegation-bot(?::[A-Za-z0-9_.-]+)+")


def _embedded_issue_marker(text: str) -> str | None:
    match = ISSUE_MARKER_RE.search(text)
    return match.group(0) if match else None


class GitHubIssueDryRunAdapter(ContractBackedDryRunAdapter):
    """Dry-run adapter for planning GitHub Issue creation or updates."""

    def __init__(self) -> None:
        super().__init__(_contract_or_raise("github.issue"))

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        repository = _string_input(request, "repository")
        title = _string_input(request, "issue_title", "Untitled planned issue")
        body = _string_input(request, "issue_body")
        marker = self.issue_marker(request)
        return {
            "github.issue": {
                "operation": "create_or_update",
                "repository": repository or None,
                "title": title,
                "body_preview": body[:240],
                "issue_marker": marker,
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            }
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        evidence: JsonMap = {"issue_marker": self.issue_marker(request)}
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence

    def build_events(
        self,
        request: AdapterRequest,
        status: str,
        missing_inputs: tuple[str, ...],
        outputs: JsonMap,
        evidence: JsonMap,
    ) -> tuple[AdapterEvent, ...]:
        issue = outputs["github.issue"]
        base_details = {
            "adapter": self.contract.id,
            "contract_kind": self.contract.kind,
            "risk": self.contract.risk,
            "dry_run": True,
            "repository": issue["repository"],
            "title": issue["title"],
            "missing_inputs": list(missing_inputs),
            "evidence_keys": sorted(evidence),
        }
        events: list[AdapterEvent] = []
        for event_type in self.contract.planned_event_types:
            details = dict(base_details)
            if event_type == "github.issue.planned":
                details["issue_marker"] = issue["issue_marker"]
            events.append(
                AdapterEvent(
                    type=event_type,
                    status=status,
                    action_id=request.action_id,
                    message=f"Dry-run planned GitHub Issue event `{event_type}`.",
                    details=details,
                )
            )
        return tuple(events)

    def issue_marker(self, request: AdapterRequest) -> str:
        body = _string_input(request, "issue_body")
        embedded = _embedded_issue_marker(body)
        if embedded:
            return embedded
        repository = _string_input(request, "repository", "unknown-repository")
        title = _string_input(request, "issue_title", request.action_id)
        raw = f"{repository}|{title}|{request.action_id}".encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()[:12]
        return f"delegation-bot:{digest}"


class SampleEchoDryRunAdapter(ContractBackedDryRunAdapter):
    """No-network adapter for local development and contributor examples."""

    def __init__(self) -> None:
        super().__init__(_contract_or_raise("sample.echo"))

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        message = _string_input(request, "message")
        label = _string_input(request, "label", "sample")
        echo_hash = self.echo_hash(request)
        return {
            "sample.echo": {
                "label": label,
                "message": message,
                "message_length": len(message),
                "echo_hash": echo_hash,
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            }
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        evidence: JsonMap = {"echo_hash": self.echo_hash(request)}
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence

    def build_events(
        self,
        request: AdapterRequest,
        status: str,
        missing_inputs: tuple[str, ...],
        outputs: JsonMap,
        evidence: JsonMap,
    ) -> tuple[AdapterEvent, ...]:
        echo = outputs["sample.echo"]
        base_details = {
            "adapter": self.contract.id,
            "contract_kind": self.contract.kind,
            "risk": self.contract.risk,
            "dry_run": True,
            "label": echo["label"],
            "missing_inputs": list(missing_inputs),
            "evidence_keys": sorted(evidence),
        }
        events: list[AdapterEvent] = []
        for event_type in self.contract.planned_event_types:
            details = dict(base_details)
            if event_type == "sample.echo.planned":
                details["echo_hash"] = echo["echo_hash"]
                details["message_length"] = echo["message_length"]
            events.append(
                AdapterEvent(
                    type=event_type,
                    status=status,
                    action_id=request.action_id,
                    message=f"Dry-run planned sample echo event `{event_type}`.",
                    details=details,
                )
            )
        return tuple(events)

    def echo_hash(self, request: AdapterRequest) -> str:
        message = _string_input(request, "message")
        label = _string_input(request, "label", "sample")
        raw = f"{label}|{message}|{request.action_id}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]


class GitHubActionsDryRunAdapter(ContractBackedDryRunAdapter):
    """Dry-run adapter for planning a GitHub Actions workflow run."""

    def __init__(self) -> None:
        super().__init__(_contract_or_raise("github.actions"))

    def workflow_run_id(self, request: AdapterRequest) -> str:
        repository = _string_input(request, "repository", "unknown-repository")
        workflow_ref = _string_input(request, "workflow_ref", "unknown-workflow")
        return f"dryrun-gha-{_json_digest(self.contract.id, request.action_id, repository, workflow_ref)}"

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        repository = _string_input(request, "repository", "unknown-repository")
        workflow_ref = _string_input(request, "workflow_ref", "unknown-workflow")
        workflow_run_id = self.workflow_run_id(request)
        conclusion = "planned" if not missing_inputs else "blocked"
        return {
            "test_result": {
                "conclusion": conclusion,
                "repository": repository,
                "workflow_ref": workflow_ref,
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            },
            "workflow_run": {
                "workflow_run_id": workflow_run_id,
                "repository": repository,
                "workflow_ref": workflow_ref,
                "status": "planned",
                "dry_run": True,
            },
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        evidence: JsonMap = {
            "workflow_run_id": self.workflow_run_id(request),
            "conclusion": "planned" if not missing_inputs else "blocked",
        }
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence


class McpToolDryRunAdapter(ContractBackedDryRunAdapter):
    """Dry-run adapter for planning an MCP tool call."""

    def __init__(self) -> None:
        super().__init__(_contract_or_raise("mcp.tool"))

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        server = _string_input(request, "server", "unknown-server")
        tool_name = _string_input(request, "tool_name", "unknown-tool")
        arguments = _input_value(request, "arguments", {})
        result_id = _json_digest(self.contract.id, request.action_id, server, tool_name, arguments)
        return {
            "tool_result": {
                "server": server,
                "tool_name": tool_name,
                "arguments_preview": _preview(arguments),
                "planned_result_id": result_id,
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            }
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        outputs = self.build_outputs(request, missing_inputs)
        evidence: JsonMap = {
            "tool_name": outputs["tool_result"]["tool_name"],
            "tool_result": outputs["tool_result"]["planned_result_id"],
        }
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence


class OpenAIAgentsDryRunAdapter(ContractBackedDryRunAdapter):
    """Dry-run adapter for planning an OpenAI Agents SDK workflow."""

    def __init__(self) -> None:
        super().__init__(_contract_or_raise("openai.agents"))

    def trace_id(self, request: AdapterRequest) -> str:
        return f"trace_{_json_digest(self.contract.id, request.action_id, request.inputs, length=20)}"

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        model = _string_input(request, "model", "unknown-model")
        tools = _list_input(request, "tools")
        instructions = _string_input(request, "instructions")
        trace_id = self.trace_id(request)
        return {
            "agent_result": {
                "model": model,
                "tool_count": len(tools),
                "instructions_preview": instructions[:240],
                "planned_final_output": "dry-run agent result",
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            },
            "trace": {
                "trace_id": trace_id,
                "adapter": self.contract.id,
                "dry_run": True,
            },
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        evidence: JsonMap = {
            "trace_id": self.trace_id(request),
            "final_output": "dry-run agent result",
        }
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence


class AnthropicMessagesDryRunAdapter(ContractBackedDryRunAdapter):
    """Dry-run adapter for planning an Anthropic Messages API call."""

    def __init__(self) -> None:
        super().__init__(_contract_or_raise("anthropic.messages"))

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        model = _string_input(request, "model", "unknown-model")
        messages = _list_input(request, "messages")
        tools = _list_input(request, "tools")
        response_id = f"msg_{_json_digest(self.contract.id, request.action_id, request.inputs, length=20)}"
        usage = {
            "input_message_count": len(messages),
            "planned_tool_count": len(tools),
            "estimated": True,
        }
        return {
            "model_response": {
                "id": response_id,
                "model": model,
                "content_preview": "dry-run model response",
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            },
            "tool_calls": {
                "planned_count": len(tools),
                "tools_preview": [_preview(tool, 120) for tool in tools],
            },
            "usage": usage,
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        outputs = self.build_outputs(request, missing_inputs)
        evidence: JsonMap = {
            "model": outputs["model_response"]["model"],
            "usage": outputs["usage"],
            "final_output": outputs["model_response"]["content_preview"],
        }
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence


class CodexThreadDryRunAdapter(ContractBackedDryRunAdapter):
    """Dry-run adapter for planning a Codex thread handoff."""

    def __init__(self) -> None:
        super().__init__(_contract_or_raise("codex.thread"))

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        objective = _string_input(request, "objective", request.objective)
        repository = _string_input(request, "repository", "unknown-repository")
        allowed_files = [str(item) for item in _list_input(request, "allowed_files")]
        patch_id = f"patch_{_json_digest(self.contract.id, request.action_id, objective, allowed_files, length=20)}"
        changed_files = allowed_files[:5] or ["dry-run:no-files-selected"]
        return {
            "patch": {
                "patch_id": patch_id,
                "repository": repository,
                "allowed_files": allowed_files,
                "planned_changed_files": changed_files,
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            },
            "summary": {
                "objective_preview": objective[:240],
                "qa_plan": "dry-run only; run project QA before promotion",
                "dry_run": True,
            },
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        outputs = self.build_outputs(request, missing_inputs)
        evidence: JsonMap = {
            "changed_files": outputs["patch"]["planned_changed_files"],
            "qa_result": "planned:not-run",
        }
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence


class ClaudeCodeDryRunAdapter(ContractBackedDryRunAdapter):
    """Dry-run adapter for planning a Claude Code handoff."""

    def __init__(self) -> None:
        super().__init__(_contract_or_raise("claude.code"))

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        objective = _string_input(request, "objective", request.objective)
        repository = _string_input(request, "repository", "unknown-repository")
        allowed_files = [str(item) for item in _list_input(request, "allowed_files")]
        mcp_servers = [str(item) for item in _list_input(request, "mcp_servers")]
        patch_id = f"patch_{_json_digest(self.contract.id, request.action_id, objective, allowed_files, length=20)}"
        changed_files = allowed_files[:5] or ["dry-run:no-files-selected"]
        return {
            "patch": {
                "patch_id": patch_id,
                "repository": repository,
                "allowed_files": allowed_files,
                "planned_changed_files": changed_files,
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            },
            "summary": {
                "objective_preview": objective[:240],
                "mcp_server_count": len(mcp_servers),
                "qa_plan": "dry-run only; run project QA before promotion",
            },
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        outputs = self.build_outputs(request, missing_inputs)
        evidence: JsonMap = {
            "changed_files": outputs["patch"]["planned_changed_files"],
            "qa_result": "planned:not-run",
        }
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence


class LocalClassifierDryRunAdapter(ContractBackedDryRunAdapter):
    """Dry-run adapter for planning a local risk-classification step."""

    def __init__(self) -> None:
        super().__init__(_contract_or_raise("local.classifier"))

    def classification(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> str:
        if missing_inputs:
            return "blocked"
        raw = f"{_preview(_input_value(request, 'plan', ''))} {_preview(_input_value(request, 'policy', ''))}".lower()
        if any(term in raw for term in ("deploy", "secret", "production", "external", "write")):
            return "medium"
        return "low"

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        classification = self.classification(request, missing_inputs)
        risk_score = {"low": 0.2, "medium": 0.6, "blocked": 0.0}.get(classification, 0.5)
        return {
            "risk_score": {
                "score": risk_score,
                "scale": "0.0-1.0",
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            },
            "classification": {
                "label": classification,
                "plan_preview": _preview(_input_value(request, "plan", "")),
                "policy_preview": _preview(_input_value(request, "policy", "")),
                "dry_run": True,
            },
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        evidence: JsonMap = {"classification": self.classification(request, missing_inputs)}
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence


class LangGraphDryRunAdapter(ContractBackedDryRunAdapter):
    """Dry-run adapter for planning a durable LangGraph workflow run."""

    def __init__(self) -> None:
        super().__init__(_contract_or_raise("langgraph.graph"))

    def checkpoint_id(self, request: AdapterRequest) -> str:
        graph_id = _string_input(request, "graph_id", "unknown-graph")
        checkpoint = _input_value(request, "checkpoint", {})
        state = _input_value(request, "state", {})
        return f"checkpoint_{_json_digest(self.contract.id, request.action_id, graph_id, checkpoint, state, length=20)}"

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        graph_id = _string_input(request, "graph_id", "unknown-graph")
        checkpoint = _input_value(request, "checkpoint", {})
        state = _input_value(request, "state", {})
        checkpoint_id = self.checkpoint_id(request)
        return {
            "graph_state": {
                "graph_id": graph_id,
                "state_preview": _preview(state),
                "planned_checkpoint_id": checkpoint_id,
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            },
            "checkpoint": {
                "checkpoint_id": checkpoint_id,
                "previous_checkpoint_preview": _preview(checkpoint),
                "status": "planned" if not missing_inputs else "blocked",
                "dry_run": True,
            },
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        evidence: JsonMap = {"checkpoint_id": self.checkpoint_id(request)}
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence


class HumanApprovalDryRunAdapter(ContractBackedDryRunAdapter):
    """Dry-run adapter for planning a human approval checkpoint."""

    def __init__(self) -> None:
        super().__init__(_contract_or_raise("human.approval"))

    def approval_id(self, request: AdapterRequest) -> str:
        approver = _string_input(request, "approver", "unknown-approver")
        approval_request = _string_input(request, "request", request.objective)
        return f"approval_{_json_digest(self.contract.id, request.action_id, approver, approval_request, length=20)}"

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        approval_request = _string_input(request, "request", request.objective)
        approver = _string_input(request, "approver", "unknown-approver")
        approval_status = "requested" if not missing_inputs else "blocked"
        return {
            "approval": {
                "approval_id": self.approval_id(request),
                "approver": approver,
                "request_preview": approval_request[:240],
                "approval_status": approval_status,
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            }
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        evidence: JsonMap = {
            "approver": _string_input(request, "approver", "unknown-approver"),
            "approval_status": "requested" if not missing_inputs else "blocked",
        }
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence


class OpenClawGatewayDryRunAdapter(ContractBackedDryRunAdapter):
    """Dry-run adapter for planning an OpenClaw-style gateway handoff."""

    def __init__(self) -> None:
        super().__init__(_contract_or_raise("openclaw.gateway"))

    def assistant_result_id(self, request: AdapterRequest) -> str:
        channel = _string_input(request, "channel", "local")
        objective = _string_input(request, "objective", request.objective)
        tools = _list_input(request, "tools")
        return f"assistant_{_json_digest(self.contract.id, request.action_id, channel, objective, tools, length=20)}"

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        channel = _string_input(request, "channel", "local")
        objective = _string_input(request, "objective", request.objective)
        tools = _list_input(request, "tools")
        return {
            "assistant_result": {
                "channel": channel,
                "objective_preview": objective[:240],
                "planned_result_id": self.assistant_result_id(request),
                "tool_count": len(tools),
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            }
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        evidence: JsonMap = {
            "channel": _string_input(request, "channel", "local"),
            "assistant_result": self.assistant_result_id(request),
        }
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence


class HermesAgentDryRunAdapter(ContractBackedDryRunAdapter):
    """Dry-run adapter for planning a Hermes-style skill-learning agent step."""

    def __init__(self) -> None:
        super().__init__(_contract_or_raise("hermes.agent"))

    def skill_id(self, request: AdapterRequest) -> str:
        objective = _string_input(request, "objective", request.objective)
        memory_scope = _string_input(request, "memory_scope", "session")
        skill_context = _input_value(request, "skill_context", {})
        return f"skill_{_json_digest(self.contract.id, request.action_id, objective, memory_scope, skill_context, length=20)}"

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        objective = _string_input(request, "objective", request.objective)
        memory_scope = _string_input(request, "memory_scope", "session")
        skill_context = _input_value(request, "skill_context", {})
        skill_id = self.skill_id(request)
        planned_result = f"dry-run agent result for {skill_id}"
        return {
            "skill_update": {
                "skill_id": skill_id,
                "memory_scope": memory_scope,
                "skill_context_preview": _preview(skill_context),
                "status": "planned" if not missing_inputs else "blocked",
                "dry_run": True,
            },
            "agent_result": {
                "objective_preview": objective[:240],
                "planned_final_output": planned_result,
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            },
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        skill_id = self.skill_id(request)
        evidence: JsonMap = {
            "skill_id": skill_id,
            "agent_result": f"dry-run agent result for {skill_id}",
        }
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence


BUILT_IN_DRY_RUN_ADAPTERS: dict[str, Adapter] = {
    "anthropic.messages": AnthropicMessagesDryRunAdapter(),
    "claude.code": ClaudeCodeDryRunAdapter(),
    "codex.thread": CodexThreadDryRunAdapter(),
    "github.actions": GitHubActionsDryRunAdapter(),
    "github.issue": GitHubIssueDryRunAdapter(),
    "hermes.agent": HermesAgentDryRunAdapter(),
    "human.approval": HumanApprovalDryRunAdapter(),
    "langgraph.graph": LangGraphDryRunAdapter(),
    "local.classifier": LocalClassifierDryRunAdapter(),
    "mcp.tool": McpToolDryRunAdapter(),
    "openai.agents": OpenAIAgentsDryRunAdapter(),
    "openclaw.gateway": OpenClawGatewayDryRunAdapter(),
    "sample.echo": SampleEchoDryRunAdapter(),
}


def get_builtin_adapter(adapter_id: str) -> Adapter | None:
    """Return a built-in dry-run adapter implementation when one exists."""

    return BUILT_IN_DRY_RUN_ADAPTERS.get(adapter_id)


def list_builtin_adapters() -> list[Adapter]:
    """Return built-in dry-run adapter implementations sorted by id."""

    return [BUILT_IN_DRY_RUN_ADAPTERS[key] for key in sorted(BUILT_IN_DRY_RUN_ADAPTERS)]
