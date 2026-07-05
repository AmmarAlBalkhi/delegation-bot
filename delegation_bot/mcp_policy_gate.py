"""MCP tool policy gate reports."""

from __future__ import annotations

import typing as T
from dataclasses import dataclass, field

from delegation_bot.evals import eval_ledger_is_valid, eval_mcp_tool_risk_review, eval_required_adapter_evidence
from delegation_bot.harness_manifest import Manifest
from delegation_bot.harness_plan import ExecutionPlan, PlanAction


JsonMap = dict[str, T.Any]


@dataclass(frozen=True)
class McpPolicyGate:
    id: str
    status: str
    message: str
    next_action: str | None = None

    def to_dict(self) -> JsonMap:
        return {
            "id": self.id,
            "status": self.status,
            "message": self.message,
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class McpToolDraft:
    action_id: str
    server: str
    tool_name: str
    arguments_preview: T.Any = None
    permission_scope: str = "unknown"
    risk_level: str = "unknown"
    prompt_injection_risk: str = "unknown"
    recommended_gate: str = "unknown"
    risk_reasons: tuple[str, ...] = ()
    approved: bool = False

    @property
    def tool_ref(self) -> str:
        return f"{self.server}/{self.tool_name}"

    def to_dict(self) -> JsonMap:
        return {
            "action_id": self.action_id,
            "server": self.server,
            "tool_name": self.tool_name,
            "tool_ref": self.tool_ref,
            "arguments_preview": self.arguments_preview,
            "permission_scope": self.permission_scope,
            "risk_level": self.risk_level,
            "prompt_injection_risk": self.prompt_injection_risk,
            "recommended_gate": self.recommended_gate,
            "risk_reasons": list(self.risk_reasons),
            "approved": self.approved,
        }


@dataclass(frozen=True)
class McpPolicyReport:
    status: str
    ledger_source: str
    drafts: tuple[McpToolDraft, ...]
    gates: tuple[McpPolicyGate, ...] = field(default_factory=tuple)

    @property
    def blocked(self) -> bool:
        return any(gate.status == "blocked" for gate in self.gates)

    def to_dict(self) -> JsonMap:
        return {
            "status": self.status,
            "ledger_source": self.ledger_source,
            "blocked": self.blocked,
            "drafts": [draft.to_dict() for draft in self.drafts],
            "gates": [gate.to_dict() for gate in self.gates],
        }


def build_mcp_policy_report(
    manifest: Manifest,
    plan: ExecutionPlan,
    ledger_events: T.Sequence[JsonMap],
    *,
    ledger_source: str,
) -> McpPolicyReport:
    drafts = tuple(_mcp_tool_drafts(plan, ledger_events))
    gates = tuple(
        [
            _draft_gate(drafts),
            *_ledger_gates(ledger_events),
            _server_allowlist_gate(manifest, drafts),
            _tool_allowlist_gate(manifest, drafts),
            _risk_gate(ledger_events, drafts),
        ]
    )
    blocked = any(gate.status == "blocked" for gate in gates)
    return McpPolicyReport(
        status="blocked" if blocked else "ready",
        ledger_source=ledger_source,
        drafts=drafts,
        gates=gates,
    )


def render_mcp_policy_report(report: McpPolicyReport) -> str:
    lines = [
        "MCP Tool Policy Gate",
        "",
        f"Status: {report.status}",
        f"Ledger: {report.ledger_source}",
        f"Tool drafts: {len(report.drafts)}",
        "",
        "Gates:",
    ]
    for gate in report.gates:
        prefix = "PASS" if gate.status == "passed" else "BLOCKED"
        lines.append(f"- [{prefix}] {gate.id}: {gate.message}")
        if gate.next_action:
            lines.append(f"  next: {gate.next_action}")

    lines.extend(["", "Tool drafts:"])
    if report.drafts:
        for draft in report.drafts:
            approval = " approved" if draft.approved else ""
            lines.append(f"- {draft.tool_ref}{approval}")
            lines.append(f"  action: {draft.action_id}")
            lines.append(
                "  risk: "
                f"{draft.risk_level}; permission={draft.permission_scope}; prompt_injection={draft.prompt_injection_risk}; "
                f"gate={draft.recommended_gate}"
            )
            if draft.risk_reasons:
                lines.append(f"  why: {'; '.join(draft.risk_reasons)}")
    else:
        lines.append("- none")

    lines.extend(["", "Next:"])
    if report.blocked:
        lines.append("Fix blocked gates, then rerun the MCP policy gate.")
    else:
        lines.append("MCP tool policy is ready for this dry-run plan.")
    return "\n".join(lines)


def _mcp_tool_drafts(plan: ExecutionPlan, ledger_events: T.Sequence[JsonMap]) -> T.Iterator[McpToolDraft]:
    evidence_by_action = _mcp_evidence_by_action(ledger_events)
    approved = _approved_action_ids(ledger_events)
    for action in plan.actions:
        if action.adapter != "mcp.tool" or not action.type.startswith("adapter.mcp.tool."):
            continue
        inputs = _executor_inputs(action)
        evidence = evidence_by_action.get(action.id, {})
        output = evidence.get("output") if isinstance(evidence.get("output"), dict) else {}
        tool_result = output.get("tool_result") if isinstance(output.get("tool_result"), dict) else {}
        yield McpToolDraft(
            action_id=action.id,
            server=str(inputs.get("server") or tool_result.get("server") or "unknown-server"),
            tool_name=str(inputs.get("tool_name") or evidence.get("tool_name") or tool_result.get("tool_name") or "unknown-tool"),
            arguments_preview=tool_result.get("arguments_preview"),
            permission_scope=str(evidence.get("permission_scope") or tool_result.get("permission_scope") or "unknown"),
            risk_level=str(evidence.get("risk_level") or tool_result.get("risk_level") or "unknown"),
            prompt_injection_risk=str(
                evidence.get("prompt_injection_risk") or tool_result.get("prompt_injection_risk") or "unknown"
            ),
            recommended_gate=str(evidence.get("recommended_gate") or tool_result.get("recommended_gate") or "unknown"),
            risk_reasons=tuple(str(item) for item in tool_result.get("risk_reasons", []) if isinstance(item, str)),
            approved=action.id in approved,
        )


def _draft_gate(drafts: T.Sequence[McpToolDraft]) -> McpPolicyGate:
    if drafts:
        return McpPolicyGate("drafts.mcp_tools", "passed", f"{len(drafts)} MCP tool draft(s) found.")
    return McpPolicyGate(
        "drafts.mcp_tools",
        "blocked",
        "No mcp.tool executor actions were found.",
        next_action="Add an mcp.tool executor or choose a Harnessfile with MCP tool usage.",
    )


def _ledger_gates(ledger_events: T.Sequence[JsonMap]) -> list[McpPolicyGate]:
    results = [eval_ledger_is_valid(ledger_events), eval_required_adapter_evidence(ledger_events)]
    return [
        McpPolicyGate(
            id=f"eval.{result.id}",
            status="passed" if result.status == "passed" else "blocked",
            message=result.message,
            next_action=None if result.status == "passed" else "Run dry-run planning before the MCP policy gate.",
        )
        for result in results
    ]


def _server_allowlist_gate(manifest: Manifest, drafts: T.Sequence[McpToolDraft]) -> McpPolicyGate:
    if not drafts:
        return McpPolicyGate("policy.allowed_mcp_servers", "passed", "No MCP servers to check.")
    allowed = _allowed_mcp_servers(manifest)
    if not allowed:
        return McpPolicyGate(
            "policy.allowed_mcp_servers",
            "blocked",
            "No allowed MCP servers are declared.",
            next_action="Add policies.permissions.allowed_mcp_servers to the Harnessfile.",
        )
    blocked = sorted({draft.server for draft in drafts if draft.server not in allowed})
    if blocked:
        return McpPolicyGate(
            "policy.allowed_mcp_servers",
            "blocked",
            f"MCP server not allowed: {', '.join(blocked)}.",
            next_action="Add the server to allowed_mcp_servers or change the executor input.",
        )
    return McpPolicyGate("policy.allowed_mcp_servers", "passed", "All MCP servers are allowed by policy.")


def _tool_allowlist_gate(manifest: Manifest, drafts: T.Sequence[McpToolDraft]) -> McpPolicyGate:
    if not drafts:
        return McpPolicyGate("policy.allowed_mcp_tools", "passed", "No MCP tools to check.")
    allowed = _allowed_mcp_tools(manifest)
    if not allowed:
        return McpPolicyGate(
            "policy.allowed_mcp_tools",
            "blocked",
            "No allowed MCP tools are declared.",
            next_action="Add policies.permissions.allowed_mcp_tools to the Harnessfile.",
        )
    blocked = sorted(draft.tool_ref for draft in drafts if not _tool_allowed(draft, allowed))
    if blocked:
        return McpPolicyGate(
            "policy.allowed_mcp_tools",
            "blocked",
            f"MCP tool not allowed: {', '.join(blocked)}.",
            next_action="Add server/tool entries to allowed_mcp_tools or change the executor input.",
        )
    return McpPolicyGate("policy.allowed_mcp_tools", "passed", "All MCP tools are allowed by policy.")


def _risk_gate(ledger_events: T.Sequence[JsonMap], drafts: T.Sequence[McpToolDraft]) -> McpPolicyGate:
    result = eval_mcp_tool_risk_review(ledger_events)
    if result.status == "passed":
        return McpPolicyGate("eval.mcp_tool_risk_review", "passed", result.message)
    missing_approval = [draft.action_id for draft in drafts if _requires_approval(draft) and not draft.approved]
    if not missing_approval:
        return McpPolicyGate(
            "eval.mcp_tool_risk_review",
            "passed",
            "High-risk MCP tool plans have approval evidence.",
        )
    return McpPolicyGate(
        "eval.mcp_tool_risk_review",
        "blocked",
        result.message,
        next_action="Append approval.granted evidence for: " + ", ".join(missing_approval),
    )


def _requires_approval(draft: McpToolDraft) -> bool:
    return draft.risk_level == "high" or draft.prompt_injection_risk == "high" or draft.recommended_gate == "approval_required"


def _executor_inputs(action: PlanAction) -> JsonMap:
    executor = action.metadata.get("executor")
    if not isinstance(executor, dict):
        return {}
    inputs = executor.get("inputs")
    return dict(inputs) if isinstance(inputs, dict) else {}


def _mcp_evidence_by_action(events: T.Sequence[JsonMap]) -> dict[str, JsonMap]:
    records: dict[str, JsonMap] = {}
    for event in events:
        action_id = event.get("action_id")
        if not isinstance(action_id, str):
            continue
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        if details.get("adapter") != "mcp.tool":
            continue
        adapter_result = details.get("adapter_result") if isinstance(details.get("adapter_result"), dict) else {}
        evidence = adapter_result.get("evidence") if isinstance(adapter_result.get("evidence"), dict) else {}
        outputs = adapter_result.get("outputs") if isinstance(adapter_result.get("outputs"), dict) else {}
        records.setdefault(action_id, {}).update(evidence)
        records[action_id]["output"] = outputs
    return records


def _approved_action_ids(events: T.Sequence[JsonMap]) -> set[str]:
    approved: set[str] = set()
    for event in events:
        if event.get("type") != "approval.granted":
            continue
        action_id = event.get("action_id")
        if isinstance(action_id, str) and action_id.strip():
            approved.add(action_id)
    return approved


def _allowed_mcp_servers(manifest: Manifest) -> set[str]:
    permissions = _permissions(manifest)
    return _string_set(permissions.get("allowed_mcp_servers"))


def _allowed_mcp_tools(manifest: Manifest) -> set[str]:
    permissions = _permissions(manifest)
    return _string_set(permissions.get("allowed_mcp_tools"))


def _permissions(manifest: Manifest) -> JsonMap:
    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
    permissions = policies.get("permissions") if isinstance(policies.get("permissions"), dict) else {}
    return permissions


def _string_set(value: T.Any) -> set[str]:
    return {str(item) for item in value if isinstance(item, str) and item.strip()} if isinstance(value, list) else set()


def _tool_allowed(draft: McpToolDraft, allowed: set[str]) -> bool:
    refs = {
        draft.tool_name,
        draft.tool_ref,
        f"{draft.server}.{draft.tool_name}",
        f"{draft.server}:{draft.tool_name}",
    }
    return bool(refs & allowed)
