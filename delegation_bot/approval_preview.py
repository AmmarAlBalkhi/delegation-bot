#!/usr/bin/env python3
"""Human-readable approval preview cards for agent actions."""

from __future__ import annotations

import typing as T
from dataclasses import dataclass
from pathlib import Path

from delegation_bot.agent_gate import AgentGateReport, build_agent_gate_report
from delegation_bot.harness_manifest import Manifest, ManifestError, load_manifest, validate_manifest
from delegation_bot.local_workspace import (
    DEFAULT_WORKSPACE_AGENT_RUN_LEDGER,
    DEFAULT_WORKSPACE_HARNESS,
    DEFAULT_WORKSPACE_REGISTRY,
)


JsonMap = dict[str, T.Any]
APPROVAL_PREVIEW_SCHEMA_VERSION = "delegation.approval-preview.v1"


@dataclass(frozen=True)
class ApprovalPreviewReport:
    status: str
    workspace: str | None
    ledger: str | None
    agent_id: str
    action: str
    target: str
    gate: AgentGateReport
    summary: str
    can_execute: bool
    command: str | None
    warnings: tuple[str, ...] = ()

    @property
    def action_id(self) -> str:
        return f"agent_gate.{_event_id_part(self.agent_id)}.{_event_id_part(self.action)}"

    @property
    def required_approvals(self) -> tuple[str, ...]:
        return self.gate.matched_approvals or self.gate.required_approvals

    @property
    def missing_approvals(self) -> tuple[str, ...]:
        if self.gate.decision != "approval_required":
            return ()
        if self.gate.matched_approvals:
            return tuple(item for item in self.gate.matched_approvals if item not in self.gate.provided_approvals)
        return ("human.approval",)

    @property
    def next_actions(self) -> tuple[str, ...]:
        actions: list[str] = []
        if self.workspace:
            actions.append(
                f"delegation agent-gate --registry {Path(self.workspace) / DEFAULT_WORKSPACE_REGISTRY} "
                f"{self.agent_id} --action {self.action} --target {self.target}"
            )
        if self.gate.decision == "allow" and self.workspace:
            actions.append(
                f"delegation agent-run {self.agent_id} --workspace {self.workspace} "
                "--execute --confirm LOCAL_AGENT_EXECUTION"
            )
        elif self.gate.decision == "approval_required":
            actions.append("Record human approval before live action.")
            if self.ledger:
                actions.append(
                    f"delegation approval-decision --ledger {self.ledger} --action-id {self.action_id} "
                    "--decision approve --approver YOUR_NAME"
                )
        elif self.gate.decision == "block":
            actions.append(self.gate.next_action)
        else:
            actions.append("Review warnings before execution or promotion.")
        actions.append("Keep RunPrint/evidence recording attached to this action.")
        return tuple(_dedupe(actions))

    @property
    def safe_next_step(self) -> str:
        if self.gate.decision == "allow":
            return "Run under DelegationHQ control with the exact execution confirmation token."
        if self.gate.decision == "approval_required":
            return "Record a human approve/block decision before live action."
        if self.gate.decision == "block":
            return "Change the request, passport, target, or risk before trying again."
        return "Review the warning and request more evidence before increasing autonomy."

    @property
    def decision_commands(self) -> tuple[JsonMap, ...]:
        commands: list[JsonMap] = []
        if self.gate.decision == "approval_required" and self.ledger:
            commands.extend(
                [
                    {
                        "id": "approve",
                        "label": "Approve",
                        "command": (
                            f"delegation approval-decision --ledger {self.ledger} --action-id {self.action_id} "
                            "--decision approve --approver YOUR_NAME"
                        ),
                        "writes_ledger": True,
                    },
                    {
                        "id": "block",
                        "label": "Block",
                        "command": (
                            f"delegation approval-decision --ledger {self.ledger} --action-id {self.action_id} "
                            "--decision block --approver YOUR_NAME"
                        ),
                        "writes_ledger": True,
                    },
                ]
            )
        if self.gate.decision == "allow" and self.workspace:
            commands.append(
                {
                    "id": "execute",
                    "label": "Execute",
                    "command": (
                        f"delegation agent-run {self.agent_id} --workspace {self.workspace} --action {self.action} "
                        f"--target {self.target} --execute --confirm LOCAL_AGENT_EXECUTION"
                    ),
                    "writes_ledger": True,
                }
            )
        return tuple(commands)

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": APPROVAL_PREVIEW_SCHEMA_VERSION,
            "status": self.status,
            "workspace": self.workspace,
            "ledger": self.ledger,
            "agent_id": self.agent_id,
            "action": self.action,
            "target": self.target,
            "action_id": self.action_id,
            "decision": self.gate.decision,
            "risk": self.gate.effective_risk,
            "summary": self.summary,
            "can_execute": self.can_execute,
            "command": self.command,
            "safe_next_step": self.safe_next_step,
            "decision_commands": list(self.decision_commands),
            "required_approvals": list(self.required_approvals),
            "missing_approvals": list(self.missing_approvals),
            "required_evidence": list(self.gate.required_evidence),
            "missing_evidence": list(self.gate.missing_evidence),
            "provided_approvals": list(self.gate.provided_approvals),
            "provided_evidence": list(self.gate.provided_evidence),
            "gate": self.gate.to_dict(),
            "warnings": list(self.warnings),
            "next_actions": list(self.next_actions),
        }


def build_approval_preview_report(
    *,
    agent_id: str,
    action: str = "read.workspace",
    target: str = "workspace",
    workspace_root: Path | None = None,
    harnessfile: Path | None = None,
    registry_paths: T.Sequence[Path] = (),
    ledger_path: Path | None = None,
    requested_risk: str | None = None,
    approvals: T.Sequence[str] = (),
    evidence: T.Sequence[str] = (),
) -> ApprovalPreviewReport:
    """Build the app-ready human card for an agent request."""

    warnings: list[str] = []
    resolved_workspace = workspace_root.resolve() if workspace_root else None
    resolved_harnessfile = harnessfile
    resolved_registries = list(registry_paths)
    resolved_ledger = ledger_path

    if resolved_workspace is not None:
        workspace_harnessfile = resolved_workspace / DEFAULT_WORKSPACE_HARNESS
        workspace_registry = resolved_workspace / DEFAULT_WORKSPACE_REGISTRY
        if resolved_harnessfile is None and workspace_harnessfile.exists():
            resolved_harnessfile = workspace_harnessfile
        if not resolved_registries and workspace_registry.exists():
            resolved_registries.append(workspace_registry)
        if resolved_ledger is None:
            resolved_ledger = resolved_workspace / DEFAULT_WORKSPACE_AGENT_RUN_LEDGER

    manifest = None
    if resolved_harnessfile is not None:
        manifest, manifest_warnings = _load_optional_manifest(resolved_harnessfile)
        warnings.extend(manifest_warnings)

    gate = build_agent_gate_report(
        agent_id=agent_id,
        action=action,
        target=target,
        manifest=manifest,
        manifest_source=str(resolved_harnessfile) if resolved_harnessfile else None,
        registry_paths=tuple(resolved_registries),
        requested_risk=requested_risk,
        provided_approvals=approvals,
        provided_evidence=evidence,
    )
    command = _command_from_gate(gate)
    return ApprovalPreviewReport(
        status=gate.status,
        workspace=str(resolved_workspace) if resolved_workspace else None,
        ledger=str(resolved_ledger) if resolved_ledger else None,
        agent_id=agent_id,
        action=gate.action,
        target=gate.target,
        gate=gate,
        summary=_summary(gate),
        can_execute=gate.decision == "allow",
        command=command,
        warnings=tuple([*warnings, *gate.registry_warnings]),
    )


def render_approval_preview_report(report: ApprovalPreviewReport) -> str:
    lines = [
        "Agent Approval Preview",
        "",
        f"Status: {report.status}",
        f"Decision: {report.gate.decision}",
        f"Agent: {report.agent_id}",
        f"Action: {report.action}",
        f"Target: {report.target}",
        f"Risk: {report.gate.effective_risk}",
        f"Can execute now: {str(report.can_execute).lower()}",
    ]
    if report.workspace:
        lines.append(f"Workspace: {report.workspace}")
    if report.ledger:
        lines.append(f"Ledger: {report.ledger}")
    if report.command:
        lines.append(f"Command: {report.command}")

    lines.extend(["", "Plain language:", f"- {report.summary}"])
    lines.append(f"- Safe next step: {report.safe_next_step}")
    if report.gate.passport:
        lines.append(f"- Runtime: {report.gate.passport.runtime_type}; autonomy: {report.gate.passport.autonomy_level}.")

    lines.extend(["", "Approvals:"])
    if report.required_approvals:
        lines.extend(f"- required: {item}" for item in report.required_approvals)
    else:
        lines.append("- required: none")
    if report.missing_approvals:
        lines.extend(f"- missing: {item}" for item in report.missing_approvals)

    lines.extend(["", "Evidence:"])
    if report.gate.required_evidence:
        lines.extend(f"- required: {item}" for item in report.gate.required_evidence)
    else:
        lines.append("- required: none")
    if report.gate.missing_evidence:
        lines.extend(f"- not yet present: {item}" for item in report.gate.missing_evidence)

    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)

    if report.decision_commands:
        lines.extend(["", "Decision commands:"])
        for command in report.decision_commands:
            lines.append(f"- {command['label']}: {command['command']}")

    lines.extend(["", "Next:"])
    lines.extend(f"- {action}" for action in report.next_actions)
    return "\n".join(lines)


def _load_optional_manifest(path: Path) -> tuple[Manifest | None, list[str]]:
    try:
        manifest = load_manifest(path)
    except (OSError, ManifestError) as exc:
        return None, [f"Harnessfile could not be loaded: {exc}"]
    errors = validate_manifest(manifest)
    if errors:
        return None, [f"Harnessfile is invalid: {error}" for error in errors]
    return manifest, []


def _summary(gate: AgentGateReport) -> str:
    if gate.decision == "allow":
        return "This agent request is inside its passport and can run after explicit execution confirmation."
    if gate.decision == "approval_required":
        return "This agent request is allowed by scope, but a human must approve before live action."
    if gate.decision == "block":
        return "This agent request is blocked before execution because identity, scope, risk, or policy failed."
    return "This agent request is possible, but warnings should be reviewed before execution."


def _command_from_gate(gate: AgentGateReport) -> str | None:
    if not gate.passport:
        return None
    endpoint = gate.passport.endpoint
    if endpoint.get("type") != "command":
        return None
    value = endpoint.get("value")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _event_id_part(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    return "_".join(part for part in cleaned.split("_") if part) or "unknown"


def _dedupe(values: T.Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
