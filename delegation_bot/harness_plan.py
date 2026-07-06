#!/usr/bin/env python3
"""Compile Harnessfiles into dry-run execution plans and ledgers."""

from __future__ import annotations

import json
import typing as T
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from delegation_bot.adapter_sdk import AdapterRequest, validate_adapter_result
from delegation_bot.adapters import get_adapter_contract
from delegation_bot.builtin_adapters import get_builtin_adapter
from delegation_bot.harness_manifest import Manifest, validate_manifest


JsonMap = dict[str, T.Any]


class PlanError(ValueError):
    """Raised when a Harnessfile cannot be compiled into a plan."""


@dataclass(frozen=True)
class PlanAction:
    id: str
    type: str
    title: str
    description: str
    actor: str = "delegationhq"
    adapter: str | None = None
    risk: str = "low"
    requires_approval: bool = False
    depends_on: tuple[str, ...] = ()
    metadata: JsonMap = field(default_factory=dict)

    def to_dict(self) -> JsonMap:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "actor": self.actor,
            "adapter": self.adapter,
            "risk": self.risk,
            "requires_approval": self.requires_approval,
            "depends_on": list(self.depends_on),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ExecutionPlan:
    id: str
    objective: str
    source: str
    mode: str
    actions: tuple[PlanAction, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> JsonMap:
        return {
            "id": self.id,
            "objective": self.objective,
            "source": self.source,
            "mode": self.mode,
            "warnings": list(self.warnings),
            "actions": [action.to_dict() for action in self.actions],
        }


@dataclass(frozen=True)
class LedgerEvent:
    run_id: str
    sequence: int
    timestamp: str
    type: str
    status: str
    message: str
    action_id: str | None = None
    details: JsonMap = field(default_factory=dict)

    def to_dict(self) -> JsonMap:
        return {
            "run_id": self.run_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "type": self.type,
            "status": self.status,
            "message": self.message,
            "action_id": self.action_id,
            "details": self.details,
        }


def _as_list(value: T.Any) -> list[T.Any]:
    return value if isinstance(value, list) else []


def _string(value: T.Any, default: str = "") -> str:
    return value if isinstance(value, str) and value.strip() else default


def _output_type(output: T.Any) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, dict):
        return _string(output.get("type"), "unknown")
    return "unknown"


def _approval_required(action_type: str, approvals: set[str]) -> bool:
    approval_aliases = {
        "output.prepare.github.pull_request": "pull_request",
        "output.prepare.github.issue": "issue",
        "adapter.github.actions.prepare": "workflow",
        "adapter.codex.thread.prepare": "agent_execution",
        "adapter.openai.agents.prepare": "agent_execution",
        "adapter.mcp.tool.prepare": "tool_call",
    }
    required_name = approval_aliases.get(action_type)
    return bool(required_name and required_name in approvals)


def _contract_approval_required(adapter: str, approvals: set[str]) -> bool:
    contract = get_adapter_contract(adapter)
    if not contract:
        return False
    return any(item in approvals for item in contract.approval_required_for)


def _adapter_inputs_from_action(action: PlanAction) -> JsonMap:
    executor = action.metadata.get("executor")
    contract = action.metadata.get("adapter_contract")
    inputs: JsonMap = {}
    if isinstance(executor, dict):
        explicit_inputs = executor.get("inputs")
        if isinstance(explicit_inputs, dict):
            inputs.update(explicit_inputs)
        if isinstance(contract, dict):
            for input_name in _as_list(contract.get("inputs")):
                if isinstance(input_name, str) and input_name in executor and input_name not in inputs:
                    inputs[input_name] = executor[input_name]
    return inputs


def _adapter_request_from_action(plan: ExecutionPlan, action: PlanAction) -> AdapterRequest:
    return AdapterRequest(
        adapter_id=str(action.adapter),
        action_id=action.id,
        mission_id=plan.id,
        objective=plan.objective,
        inputs=_adapter_inputs_from_action(action),
        metadata={"action": action.to_dict()},
        dry_run=True,
    )


def compile_plan(manifest: Manifest, source: str = "<memory>") -> ExecutionPlan:
    errors = validate_manifest(manifest)
    if errors:
        raise PlanError("; ".join(errors))

    plan_id = _string(manifest.get("id"), "unnamed")
    objective = _string(manifest.get("objective"), "No objective provided")
    actions: list[PlanAction] = []
    warnings: list[str] = []

    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
    approvals_cfg = policies.get("approvals") if isinstance(policies, dict) else {}
    required_for = approvals_cfg.get("required_for") if isinstance(approvals_cfg, dict) else []
    approvals = {str(item) for item in _as_list(required_for)}

    for index, trigger in enumerate(_as_list(manifest.get("triggers"))):
        if not isinstance(trigger, dict):
            continue
        trigger_type = _string(trigger.get("type"), "unknown")
        actions.append(
            PlanAction(
                id=f"trigger.{index + 1}",
                type="trigger.observe",
                title=f"Observe trigger `{trigger_type}`",
                description="Register the trigger that can start this delegated mission.",
                metadata={"trigger": trigger},
            )
        )

    context = manifest.get("context") if isinstance(manifest.get("context"), dict) else {}
    for index, source_cfg in enumerate(_as_list(context.get("sources") if isinstance(context, dict) else [])):
        if not isinstance(source_cfg, dict):
            continue
        source_id = _string(source_cfg.get("id"), f"source_{index + 1}")
        actions.append(
            PlanAction(
                id=f"context.{source_id}",
                type="context.load",
                title=f"Load context `{source_id}`",
                description="Resolve declared context before any executor runs.",
                metadata={"context": source_cfg},
            )
        )

    for index, capability_pack in enumerate(_as_list(manifest.get("capability_packs"))):
        if not isinstance(capability_pack, dict):
            continue
        pack_id = _string(capability_pack.get("id"), f"pack_{index + 1}")
        capabilities = _as_list(capability_pack.get("capabilities"))
        risk = "medium" if any(str(item).startswith(("write", "send", "execute", "deploy")) for item in capabilities) else "low"
        actions.append(
            PlanAction(
                id=f"capability_pack.{pack_id}",
                type="capability_pack.register",
                title=f"Register capability pack `{pack_id}`",
                description=_string(capability_pack.get("description"), "Declare a reusable bundle of agent powers."),
                risk=risk,
                metadata={"capability_pack": capability_pack},
            )
        )

    for index, model in enumerate(_as_list(manifest.get("models"))):
        if not isinstance(model, dict):
            continue
        model_id = _string(model.get("id"), f"model_{index + 1}")
        provider = _string(model.get("provider"), "unknown")
        model_name = _string(model.get("model"), "unknown")
        actions.append(
            PlanAction(
                id=f"model.{model_id}",
                type="model.configure",
                title=f"Configure model `{model_id}`",
                description=f"Prepare {provider} model `{model_name}` for its declared role.",
                adapter=_string(model.get("adapter"), provider),
                metadata={"model": model},
            )
        )

    for index, agent in enumerate(_as_list(manifest.get("agents"))):
        if not isinstance(agent, dict):
            continue
        agent_id = _string(agent.get("id"), f"agent_{index + 1}")
        runtime = _string(agent.get("runtime"), "unknown")
        autonomy_level = _string(agent.get("autonomy_level"), "suggest")
        capability_pack_ids = [
            str(pack_id)
            for pack_id in _as_list(agent.get("capability_packs"))
            if isinstance(pack_id, str)
        ]
        depends_on = tuple([f"model.{agent['model']}"] if isinstance(agent.get("model"), str) else [])
        depends_on = depends_on + tuple(f"capability_pack.{pack_id}" for pack_id in capability_pack_ids)
        requires_approval = autonomy_level in {"act", "operate", "deploy"}
        risk = "high" if autonomy_level in {"operate", "deploy"} else "medium" if requires_approval else "low"
        actions.append(
            PlanAction(
                id=f"agent.{agent_id}",
                type="agent.passport",
                title=f"Prepare agent passport `{agent_id}`",
                description=f"Bind runtime `{runtime}` to autonomy level `{autonomy_level}` and declared capability packs.",
                adapter=runtime,
                risk=risk,
                requires_approval=requires_approval,
                depends_on=depends_on,
                metadata={"agent": agent},
            )
        )

    for index, executor in enumerate(_as_list(manifest.get("executors"))):
        if not isinstance(executor, dict):
            continue
        executor_id = _string(executor.get("id"), f"executor_{index + 1}")
        adapter = _string(executor.get("adapter"), "unknown")
        action_type = f"adapter.{adapter}.prepare"
        contract = get_adapter_contract(adapter)
        requires_approval = _approval_required(action_type, approvals) or _contract_approval_required(adapter, approvals)
        risk = contract.risk if contract else "medium" if requires_approval or executor.get("kind") in {"ai_harness", "ml_model"} else "low"
        depends_on = (f"model.{executor['model']}",) if isinstance(executor.get("model"), str) else ()
        metadata = {"executor": executor}
        if contract:
            metadata["adapter_contract"] = contract.to_dict()
        actions.append(
            PlanAction(
                id=f"executor.{executor_id}",
                type=action_type,
                title=f"Prepare executor `{executor_id}`",
                description=_string(executor.get("purpose"), contract.description if contract else "Prepare executor for dry-run planning."),
                adapter=adapter,
                risk=risk,
                requires_approval=requires_approval,
                depends_on=depends_on,
                metadata=metadata,
            )
        )
        if not contract:
            warnings.append(f"No built-in adapter contract found for `{adapter}`.")

    if approvals:
        actions.append(
            PlanAction(
                id="policy.approvals",
                type="policy.approval_gate",
                title="Enforce approval policy",
                description="Block risky actions until required human approvals exist.",
                risk="medium",
                metadata={"required_for": sorted(approvals)},
            )
        )

    budgets = policies.get("budgets") if isinstance(policies, dict) else None
    if isinstance(budgets, dict) and budgets:
        actions.append(
            PlanAction(
                id="policy.budgets",
                type="policy.budget_gate",
                title="Enforce budget policy",
                description="Track declared cost and runtime budgets before execution.",
                metadata={"budgets": budgets},
            )
        )

    permissions = policies.get("permissions") if isinstance(policies, dict) else None
    if isinstance(permissions, dict) and permissions:
        actions.append(
            PlanAction(
                id="policy.permissions",
                type="policy.permission_gate",
                title="Enforce permission policy",
                description="Restrict repositories, network access, and tool surfaces.",
                risk="medium",
                metadata={"permissions": permissions},
            )
        )

    for index, output in enumerate(_as_list(manifest.get("outputs"))):
        output_type = _output_type(output)
        action_type = f"output.prepare.{output_type}"
        actions.append(
            PlanAction(
                id=f"output.{index + 1}",
                type=action_type,
                title=f"Prepare output `{output_type}`",
                description="Declare the output artifact expected from this mission.",
                requires_approval=_approval_required(action_type, approvals),
                metadata={"output": output},
            )
        )

    for index, eval_cfg in enumerate(_as_list(manifest.get("evals"))):
        if not isinstance(eval_cfg, dict):
            continue
        eval_id = _string(eval_cfg.get("id"), f"eval_{index + 1}")
        actions.append(
            PlanAction(
                id=f"eval.{eval_id}",
                type="eval.schedule",
                title=f"Schedule eval `{eval_id}`",
                description=_string(eval_cfg.get("description"), "Run declared eval against outputs and ledger."),
                metadata={"eval": eval_cfg},
            )
        )

    if not any(action.type == "output.prepare.run_ledger" for action in actions):
        warnings.append("No run_ledger output declared; dry-run ledger can still be written by the CLI.")

    return ExecutionPlan(
        id=plan_id,
        objective=objective,
        source=source,
        mode="dry-run",
        actions=tuple(actions),
        warnings=tuple(warnings),
    )


def render_plan(plan: ExecutionPlan) -> str:
    lines = [
        f"Plan: {plan.id}",
        f"Mode: {plan.mode}",
        f"Source: {plan.source}",
        f"Objective: {plan.objective}",
        "",
        "Actions:",
    ]
    for index, action in enumerate(plan.actions, start=1):
        approval = " approval-required" if action.requires_approval else ""
        adapter = f" adapter={action.adapter}" if action.adapter else ""
        lines.append(f"{index}. [{action.risk}{approval}] {action.title}{adapter}")
        lines.append(f"   type: {action.type}")
        lines.append(f"   {action.description}")
        if action.depends_on:
            lines.append(f"   depends_on: {', '.join(action.depends_on)}")
    if plan.warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in plan.warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines)


def build_dry_run_ledger(
    plan: ExecutionPlan,
    run_id: str | None = None,
    timestamp: str | None = None,
) -> list[LedgerEvent]:
    event_time = timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    ledger_run_id = run_id or f"dryrun-{plan.id}"
    events: list[LedgerEvent] = []

    def append_event(
        event_type: str,
        status: str,
        message: str,
        action_id: str | None = None,
        details: JsonMap | None = None,
    ) -> None:
        events.append(
            LedgerEvent(
                run_id=ledger_run_id,
                sequence=len(events) + 1,
                timestamp=event_time,
                type=event_type,
                status=status,
                message=message,
                action_id=action_id,
                details=details or {},
            )
        )

    append_event(
        event_type="plan.compiled",
        status="planned",
        message=f"Compiled dry-run plan `{plan.id}`.",
        details={"plan": plan.to_dict()},
    )
    for action in plan.actions:
        append_event(
            event_type=f"dry_run.{action.type}",
            status="planned",
            action_id=action.id,
            message=action.title,
            details={"action": action.to_dict()},
        )
        contract = action.metadata.get("adapter_contract")
        if not isinstance(contract, dict):
            continue
        sdk_adapter = get_builtin_adapter(action.adapter) if action.adapter else None
        if sdk_adapter:
            try:
                adapter_result = sdk_adapter.plan(_adapter_request_from_action(plan, action))
                validation_errors = validate_adapter_result(sdk_adapter.contract, adapter_result)
            except Exception as exc:  # pragma: no cover - defensive guard for third-party adapters
                append_event(
                    event_type=f"adapter.{action.adapter}.failed",
                    status="failed",
                    action_id=action.id,
                    message=f"Adapter `{action.adapter}` failed during dry-run planning.",
                    details={"adapter": action.adapter, "error": str(exc), "dry_run": True},
                )
                continue
            for adapter_event in adapter_result.ledger_events:
                details = dict(adapter_event.details)
                details["adapter_result"] = {
                    "status": adapter_result.status,
                    "message": adapter_result.message,
                    "outputs": adapter_result.outputs,
                    "evidence": adapter_result.evidence,
                    "dry_run": adapter_result.dry_run,
                }
                if validation_errors:
                    details["validation_errors"] = validation_errors
                append_event(
                    event_type=adapter_event.type,
                    status=adapter_event.status,
                    action_id=adapter_event.action_id or action.id,
                    message=adapter_event.message,
                    details=details,
                )
            continue
        for event_type in _as_list(contract.get("planned_event_types")):
            if not isinstance(event_type, str) or not event_type.strip():
                continue
            append_event(
                event_type=event_type,
                status="planned",
                action_id=action.id,
                message=f"Planned adapter contract event `{event_type}`.",
                details={
                    "adapter": action.adapter,
                    "contract": {
                        "id": contract.get("id"),
                        "kind": contract.get("kind"),
                        "risk": contract.get("risk"),
                        "required_evidence": _as_list(contract.get("required_evidence")),
                    },
                    "dry_run": True,
                },
            )
    append_event(
        event_type="dry_run.completed",
        status="planned",
        message="Dry-run plan completed without executing live actions.",
        details={"action_count": len(plan.actions), "warnings": list(plan.warnings)},
    )
    return events


def write_jsonl(events: T.Iterable[LedgerEvent], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")
