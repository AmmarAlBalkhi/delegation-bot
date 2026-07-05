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
WRITE_TOOL_RE = re.compile(
    r"(apply|build|cancel|commit|create|delete|deploy|edit|execute|merge|move|patch|post|publish|push|remove|run|send|shell|update|write)",
    re.IGNORECASE,
)
READ_TOOL_RE = re.compile(r"(get|inspect|list|query|read|retrieve|search|summarize|view)", re.IGNORECASE)
NETWORK_TOOL_RE = re.compile(r"(api|browser|fetch|http|request|url|web)", re.IGNORECASE)
SECRET_KEY_RE = re.compile(r"(api[_-]?key|credential|password|secret|token)", re.IGNORECASE)
PROMPT_SURFACE_RE = re.compile(
    r"(content|description|html|issue|markdown|message|prompt|query|text|transcript|url|webpage)",
    re.IGNORECASE,
)
PROMPT_ATTACK_RE = re.compile(
    r"(disregard|ignore|override).{0,40}(instruction|policy|previous|system)|system prompt|developer message",
    re.IGNORECASE,
)
LOCAL_PROFILE_DEFAULT = "delegation.default"
LOCAL_CLASSIFIER_PROFILES: dict[str, dict[str, tuple[str, ...]]] = {
    LOCAL_PROFILE_DEFAULT: {
        "approval_required_terms": (
            "credential",
            "delete",
            "deploy",
            "external",
            "merge",
            "production",
            "publish",
            "secret",
            "token",
            "write",
        ),
        "review_terms": ("agent", "github", "mcp", "model", "network", "pull request", "workflow"),
    },
    "release-readiness": {
        "approval_required_terms": (
            "credential",
            "deploy",
            "package",
            "production",
            "publish",
            "release",
            "secret",
            "tag",
            "token",
        ),
        "review_terms": ("changelog", "license", "package", "test", "version", "workflow"),
    },
    "code-review": {
        "approval_required_terms": (
            "auth",
            "credential",
            "delete",
            "permission",
            "secret",
            "security",
            "token",
        ),
        "review_terms": ("diff", "dependency", "mcp", "model", "test", "workflow"),
    },
}


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
        ref = _string_input(request, "ref", "main")
        inputs = _input_value(request, "inputs", {})
        return f"dryrun-gha-{_json_digest(self.contract.id, request.action_id, repository, workflow_ref, ref, inputs)}"

    def workflow_run_url(self, request: AdapterRequest) -> str:
        repository = _string_input(request, "repository", "unknown-repository")
        return f"https://github.com/{repository}/actions/runs/{self.workflow_run_id(request)}"

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        repository = _string_input(request, "repository", "unknown-repository")
        workflow_ref = _string_input(request, "workflow_ref", "unknown-workflow")
        ref = _string_input(request, "ref", "main")
        inputs = _input_value(request, "inputs", {})
        workflow_run_id = self.workflow_run_id(request)
        workflow_run_url = self.workflow_run_url(request)
        conclusion = "planned" if not missing_inputs else "blocked"
        return {
            "test_result": {
                "conclusion": conclusion,
                "repository": repository,
                "workflow_ref": workflow_ref,
                "ref": ref,
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            },
            "workflow_run": {
                "workflow_run_id": workflow_run_id,
                "workflow_run_url": workflow_run_url,
                "repository": repository,
                "workflow_ref": workflow_ref,
                "ref": ref,
                "inputs": inputs if isinstance(inputs, dict) else {},
                "status": "planned",
                "dry_run": True,
                "dispatch_preview": True,
            },
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        evidence: JsonMap = {
            "workflow_run_id": self.workflow_run_id(request),
            "workflow_run_url": self.workflow_run_url(request),
            "conclusion": "planned" if not missing_inputs else "blocked",
        }
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence


def _mcp_tool_assessment(server: str, tool_name: str, arguments: T.Any) -> JsonMap:
    text_parts = [server, tool_name, *_argument_text(arguments)]
    joined_text = " ".join(text_parts)
    keys = set(_argument_keys(arguments))
    capability_tags: set[str] = set()
    risk_reasons: list[str] = []

    if WRITE_TOOL_RE.search(tool_name) or any(WRITE_TOOL_RE.search(key) for key in keys):
        capability_tags.add("write")
        risk_reasons.append("tool name or argument keys suggest write/execute behavior")
    if NETWORK_TOOL_RE.search(joined_text):
        capability_tags.add("network")
        risk_reasons.append("tool name or arguments mention network or web access")
    if SECRET_KEY_RE.search(joined_text):
        capability_tags.add("secret_access")
        risk_reasons.append("arguments mention secret-like material")
    if _arguments_include_path(arguments):
        capability_tags.add("filesystem")
    if READ_TOOL_RE.search(tool_name) and not {"write", "secret_access"} & capability_tags:
        capability_tags.add("read")

    permission_scope = _permission_scope(capability_tags)
    prompt_injection_risk = _prompt_injection_risk(tool_name, arguments)
    if prompt_injection_risk != "low":
        risk_reasons.append(f"tool arguments expose {prompt_injection_risk} prompt-injection surface")

    risk_level = _mcp_risk_level(capability_tags, prompt_injection_risk)
    if not risk_reasons:
        risk_reasons.append("read-only local tool shape")

    recommended_gate = "approval_required" if risk_level == "high" else "review_recommended" if risk_level == "medium" else "none"
    return {
        "permission_scope": permission_scope,
        "capability_tags": sorted(capability_tags) or ["unknown"],
        "risk_level": risk_level,
        "prompt_injection_risk": prompt_injection_risk,
        "risk_reasons": risk_reasons,
        "recommended_gate": recommended_gate,
    }


def _permission_scope(capability_tags: set[str]) -> str:
    if "secret_access" in capability_tags:
        return "secret_access"
    if "write" in capability_tags and "network" in capability_tags:
        return "network_write"
    if "write" in capability_tags:
        return "write_or_execute"
    if "network" in capability_tags:
        return "network_read"
    if "filesystem" in capability_tags:
        return "filesystem_read"
    if "read" in capability_tags:
        return "read"
    return "unknown"


def _mcp_risk_level(capability_tags: set[str], prompt_injection_risk: str) -> str:
    if "secret_access" in capability_tags or "write" in capability_tags or prompt_injection_risk == "high":
        return "high"
    if not capability_tags or "network" in capability_tags or prompt_injection_risk == "medium":
        return "medium"
    return "low"


def _prompt_injection_risk(tool_name: str, arguments: T.Any) -> str:
    text_values = list(_argument_text(arguments))
    joined_text = " ".join([tool_name, *text_values])
    if PROMPT_ATTACK_RE.search(joined_text):
        return "high"
    keys = set(_argument_keys(arguments))
    if any(PROMPT_SURFACE_RE.search(key) for key in keys):
        return "medium"
    if any("http://" in value.lower() or "https://" in value.lower() for value in text_values):
        return "medium"
    return "low"


def _arguments_include_path(value: T.Any) -> bool:
    for key in _argument_keys(value):
        if key in {"file", "files", "folder", "path", "paths", "repo", "repository"}:
            return True
    return False


def _argument_keys(value: T.Any) -> T.Iterator[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from _argument_keys(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _argument_keys(item)


def _argument_text(value: T.Any) -> T.Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from _argument_text(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _argument_text(item)
    elif value is not None:
        yield str(value)


class McpToolDryRunAdapter(ContractBackedDryRunAdapter):
    """Dry-run adapter for planning an MCP tool call."""

    def __init__(self) -> None:
        super().__init__(_contract_or_raise("mcp.tool"))

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        server = _string_input(request, "server", "unknown-server")
        tool_name = _string_input(request, "tool_name", "unknown-tool")
        arguments = _input_value(request, "arguments", {})
        result_id = _json_digest(self.contract.id, request.action_id, server, tool_name, arguments)
        assessment = _mcp_tool_assessment(server, tool_name, arguments)
        return {
            "tool_result": {
                "server": server,
                "tool_name": tool_name,
                "arguments_preview": _preview(arguments),
                "planned_result_id": result_id,
                "permission_scope": assessment["permission_scope"],
                "capability_tags": assessment["capability_tags"],
                "risk_level": assessment["risk_level"],
                "prompt_injection_risk": assessment["prompt_injection_risk"],
                "risk_reasons": assessment["risk_reasons"],
                "recommended_gate": assessment["recommended_gate"],
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            }
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        outputs = self.build_outputs(request, missing_inputs)
        evidence: JsonMap = {
            "tool_name": outputs["tool_result"]["tool_name"],
            "tool_result": outputs["tool_result"]["planned_result_id"],
            "permission_scope": outputs["tool_result"]["permission_scope"],
            "risk_level": outputs["tool_result"]["risk_level"],
            "prompt_injection_risk": outputs["tool_result"]["prompt_injection_risk"],
            "recommended_gate": outputs["tool_result"]["recommended_gate"],
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

    def assessment(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        profile_id = _string_input(request, "profile", LOCAL_PROFILE_DEFAULT)
        profile = LOCAL_CLASSIFIER_PROFILES.get(profile_id) or LOCAL_CLASSIFIER_PROFILES[LOCAL_PROFILE_DEFAULT]
        raw = f"{_preview(_input_value(request, 'plan', ''))} {_preview(_input_value(request, 'policy', ''))}".lower()
        approval_matches = _matched_terms(raw, profile["approval_required_terms"])
        review_matches = _matched_terms(raw, profile["review_terms"])
        reasons: list[str] = []

        if missing_inputs:
            classification = "blocked"
            recommended_gate = "fix_missing_inputs"
            reasons.append("required classifier inputs are missing")
        elif approval_matches:
            classification = "high"
            recommended_gate = "approval_required"
            reasons.append("matched approval-required policy terms")
        elif review_matches:
            classification = "medium"
            recommended_gate = "review_recommended"
            reasons.append("matched review policy terms")
        else:
            classification = "low"
            recommended_gate = "none"
            reasons.append("no profile risk terms matched")

        if profile_id not in LOCAL_CLASSIFIER_PROFILES:
            reasons.append(f"unknown profile `{profile_id}`; used {LOCAL_PROFILE_DEFAULT}")
            profile_id = LOCAL_PROFILE_DEFAULT

        score = {"low": 0.2, "medium": 0.6, "high": 0.9, "blocked": 0.0}.get(classification, 0.5)
        return {
            "classification": classification,
            "score": score,
            "profile": profile_id,
            "recommended_gate": recommended_gate,
            "reasons": reasons,
            "matched_terms": {
                "approval_required": approval_matches,
                "review": review_matches,
            },
        }

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        assessment = self.assessment(request, missing_inputs)
        profile_id = str(assessment["profile"])
        profile = LOCAL_CLASSIFIER_PROFILES[profile_id]
        return {
            "risk_score": {
                "score": assessment["score"],
                "scale": "0.0-1.0",
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            },
            "classification": {
                "label": assessment["classification"],
                "recommended_gate": assessment["recommended_gate"],
                "policy_profile": profile_id,
                "reasons": assessment["reasons"],
                "matched_terms": assessment["matched_terms"],
                "plan_preview": _preview(_input_value(request, "plan", "")),
                "policy_preview": _preview(_input_value(request, "policy", "")),
                "dry_run": True,
            },
            "policy_profile": {
                "id": profile_id,
                "source": "deterministic",
                "approval_required_terms": list(profile["approval_required_terms"]),
                "review_terms": list(profile["review_terms"]),
                "dry_run": True,
            },
        }

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        assessment = self.assessment(request, missing_inputs)
        evidence: JsonMap = {
            "classification": assessment["classification"],
            "policy_profile": assessment["profile"],
            "recommended_gate": assessment["recommended_gate"],
        }
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence


def _matched_terms(text: str, terms: T.Iterable[str]) -> list[str]:
    return [term for term in terms if term in text]


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
