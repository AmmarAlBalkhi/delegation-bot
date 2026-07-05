#!/usr/bin/env python3
"""Adapter contracts for Delegation Bot executor runtimes."""

from __future__ import annotations

import typing as T
from dataclasses import dataclass


JsonMap = dict[str, T.Any]


@dataclass(frozen=True)
class AdapterContract:
    id: str
    kind: str
    description: str
    risk: str
    approval_required_for: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    planned_event_types: tuple[str, ...]
    required_evidence: tuple[str, ...]

    def to_dict(self) -> JsonMap:
        return {
            "id": self.id,
            "kind": self.kind,
            "description": self.description,
            "risk": self.risk,
            "approval_required_for": list(self.approval_required_for),
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "planned_event_types": list(self.planned_event_types),
            "required_evidence": list(self.required_evidence),
        }


BUILT_IN_ADAPTERS: dict[str, AdapterContract] = {
    "github.issue": AdapterContract(
        id="github.issue",
        kind="workflow",
        description="Plan GitHub Issue creation or updates.",
        risk="low",
        approval_required_for=(),
        inputs=("repository", "issue_title", "issue_body"),
        outputs=("github.issue", "run_ledger"),
        planned_event_types=("adapter.github.issue.prepare", "github.issue.planned"),
        required_evidence=("issue_marker",),
    ),
    "github.actions": AdapterContract(
        id="github.actions",
        kind="workflow",
        description="Plan GitHub Actions workflow execution and status collection.",
        risk="medium",
        approval_required_for=("workflow",),
        inputs=("repository", "workflow_ref"),
        outputs=("test_result", "workflow_run", "run_ledger"),
        planned_event_types=("adapter.github.actions.prepare", "github.actions.planned"),
        required_evidence=("workflow_run_id", "workflow_run_url", "conclusion"),
    ),
    "sample.echo": AdapterContract(
        id="sample.echo",
        kind="tool",
        description="Plan a no-network echo adapter for local development and contributor examples.",
        risk="low",
        approval_required_for=(),
        inputs=("message", "label"),
        outputs=("sample.echo", "run_ledger"),
        planned_event_types=("adapter.sample.echo.prepare", "sample.echo.planned"),
        required_evidence=("echo_hash",),
    ),
    "codex.thread": AdapterContract(
        id="codex.thread",
        kind="ai_harness",
        description="Plan a Codex coding-agent handoff.",
        risk="medium",
        approval_required_for=("agent_execution", "pull_request"),
        inputs=("objective", "repository", "allowed_files"),
        outputs=("patch", "summary", "run_ledger"),
        planned_event_types=("adapter.codex.thread.prepare", "codex.thread.planned"),
        required_evidence=("changed_files", "qa_result"),
    ),
    "openai.agents": AdapterContract(
        id="openai.agents",
        kind="ai_harness",
        description="Plan an OpenAI Agents SDK workflow.",
        risk="medium",
        approval_required_for=("agent_execution",),
        inputs=("model", "tools", "instructions"),
        outputs=("agent_result", "trace", "run_ledger"),
        planned_event_types=("adapter.openai.agents.prepare", "openai.agents.planned"),
        required_evidence=("trace_id", "final_output"),
    ),
    "anthropic.messages": AdapterContract(
        id="anthropic.messages",
        kind="model_provider",
        description="Plan an Anthropic Claude Messages API call, including optional tool use.",
        risk="medium",
        approval_required_for=("model_request", "tool_call"),
        inputs=("model", "messages", "system_prompt"),
        outputs=("model_response", "tool_calls", "usage", "run_ledger"),
        planned_event_types=("adapter.anthropic.messages.prepare", "anthropic.messages.planned"),
        required_evidence=("model", "usage", "final_output"),
    ),
    "claude.code": AdapterContract(
        id="claude.code",
        kind="ai_harness",
        description="Plan a Claude Code coding-agent handoff.",
        risk="medium",
        approval_required_for=("agent_execution", "pull_request"),
        inputs=("objective", "repository", "allowed_files"),
        outputs=("patch", "summary", "run_ledger"),
        planned_event_types=("adapter.claude.code.prepare", "claude.code.planned"),
        required_evidence=("changed_files", "qa_result"),
    ),
    "langgraph.graph": AdapterContract(
        id="langgraph.graph",
        kind="workflow",
        description="Plan a durable LangGraph workflow run.",
        risk="medium",
        approval_required_for=("workflow",),
        inputs=("graph_id", "checkpoint", "state"),
        outputs=("graph_state", "checkpoint", "run_ledger"),
        planned_event_types=("adapter.langgraph.graph.prepare", "langgraph.graph.planned"),
        required_evidence=("checkpoint_id",),
    ),
    "mcp.tool": AdapterContract(
        id="mcp.tool",
        kind="tool",
        description="Plan calls to Model Context Protocol tools.",
        risk="medium",
        approval_required_for=("tool_call",),
        inputs=("server", "tool_name", "arguments"),
        outputs=("tool_result", "run_ledger"),
        planned_event_types=("adapter.mcp.tool.prepare", "mcp.tool.planned"),
        required_evidence=("tool_name", "tool_result"),
    ),
    "openclaw.gateway": AdapterContract(
        id="openclaw.gateway",
        kind="ai_harness",
        description="Plan work routed to an OpenClaw-style local assistant gateway.",
        risk="medium",
        approval_required_for=("agent_execution", "external_message"),
        inputs=("channel", "objective", "tools"),
        outputs=("assistant_result", "run_ledger"),
        planned_event_types=("adapter.openclaw.gateway.prepare", "openclaw.gateway.planned"),
        required_evidence=("channel", "assistant_result"),
    ),
    "hermes.agent": AdapterContract(
        id="hermes.agent",
        kind="ai_harness",
        description="Plan work routed to a Hermes-style skill-learning agent.",
        risk="medium",
        approval_required_for=("agent_execution",),
        inputs=("objective", "skill_context", "memory_scope"),
        outputs=("skill_update", "agent_result", "run_ledger"),
        planned_event_types=("adapter.hermes.agent.prepare", "hermes.agent.planned"),
        required_evidence=("skill_id", "agent_result"),
    ),
    "local.classifier": AdapterContract(
        id="local.classifier",
        kind="ml_model",
        description="Plan a local classification or risk-scoring step.",
        risk="low",
        approval_required_for=(),
        inputs=("plan", "policy"),
        outputs=("risk_score", "classification", "run_ledger"),
        planned_event_types=("adapter.local.classifier.prepare", "local.classifier.planned"),
        required_evidence=("classification",),
    ),
    "human.approval": AdapterContract(
        id="human.approval",
        kind="human",
        description="Plan a human approval checkpoint.",
        risk="low",
        approval_required_for=(),
        inputs=("request", "approver"),
        outputs=("approval", "run_ledger"),
        planned_event_types=("adapter.human.approval.prepare", "human.approval.requested"),
        required_evidence=("approver", "approval_status"),
    ),
}


def get_adapter_contract(adapter_id: str) -> AdapterContract | None:
    return BUILT_IN_ADAPTERS.get(adapter_id)


def list_adapter_contracts() -> list[AdapterContract]:
    return [BUILT_IN_ADAPTERS[key] for key in sorted(BUILT_IN_ADAPTERS)]


def adapter_contract_summary(contract: AdapterContract) -> str:
    approvals = ", ".join(contract.approval_required_for) or "none"
    return f"{contract.id} ({contract.kind}, risk={contract.risk}, approvals={approvals})"


def render_adapter_contracts(contracts: T.Sequence[AdapterContract]) -> str:
    lines = ["Adapter contracts", ""]
    for contract in contracts:
        lines.append(f"- {adapter_contract_summary(contract)}")
        lines.append(f"  {contract.description}")
        lines.append(f"  outputs: {', '.join(contract.outputs)}")
    return "\n".join(lines)
