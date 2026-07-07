#!/usr/bin/env python3
"""Agent Passport action gate for Bring Your Own Agent control."""

from __future__ import annotations

import typing as T
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from delegation_bot.agent_passports import AgentPassport, build_agent_passport_report
from delegation_bot.evidence_report import build_evidence_report
from delegation_bot.harness_manifest import Manifest
from delegation_bot.harness_plan import LedgerEvent


JsonMap = dict[str, T.Any]

AGENT_GATE_SCHEMA_VERSION = "delegation.agent-gate.v1"
DECISIONS = ("allow", "warn", "approval_required", "block")
RISK_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
WRITE_VERBS = {
    "act",
    "apply",
    "cancel",
    "close",
    "commit",
    "create",
    "delete",
    "deploy",
    "dispatch",
    "edit",
    "execute",
    "force",
    "merge",
    "post",
    "publish",
    "push",
    "remove",
    "run",
    "send",
    "update",
    "write",
}
GENERIC_CAPABILITY_PREFIXES = {"read", "write", "draft", "summarize", "classify", "suggest", "retrieve"}


@dataclass(frozen=True)
class AgentGateCheck:
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
class AgentGateReport:
    decision: str
    agent_id: str
    action: str
    target: str
    requested_risk: str | None
    effective_risk: str
    passport: AgentPassport | None
    checks: tuple[AgentGateCheck, ...]
    required_approvals: tuple[str, ...] = ()
    matched_approvals: tuple[str, ...] = ()
    provided_approvals: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()
    provided_evidence: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    registry_warnings: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return self.decision == "block"

    @property
    def status(self) -> str:
        return {
            "allow": "ready",
            "warn": "warning",
            "approval_required": "approval_required",
            "block": "blocked",
        }[self.decision]

    @property
    def next_action(self) -> str:
        for status in ("blocked", "approval_required", "warning"):
            for check in self.checks:
                if check.status == status and check.next_action:
                    return check.next_action
        if self.decision == "allow":
            return "Record required evidence during execution, then run evals before promotion."
        return "Review the gate report before continuing."

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": AGENT_GATE_SCHEMA_VERSION,
            "status": self.status,
            "decision": self.decision,
            "agent": self.passport.to_dict() if self.passport else None,
            "agent_id": self.agent_id,
            "action": self.action,
            "target": self.target,
            "requested_risk": self.requested_risk,
            "effective_risk": self.effective_risk,
            "required_approvals": list(self.required_approvals),
            "matched_approvals": list(self.matched_approvals),
            "provided_approvals": list(self.provided_approvals),
            "required_evidence": list(self.required_evidence),
            "provided_evidence": list(self.provided_evidence),
            "missing_evidence": list(self.missing_evidence),
            "checks": [check.to_dict() for check in self.checks],
            "sources": list(self.sources),
            "registry_warnings": list(self.registry_warnings),
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class AgentGateAuditItem:
    gate_sequence: int | None
    agent_id: str
    action: str
    target: str
    decision: str
    gate_status: str
    evidence_status: str
    outcome: str
    message: str
    next_action: str

    def to_dict(self) -> JsonMap:
        return {
            "gate_sequence": self.gate_sequence,
            "agent_id": self.agent_id,
            "action": self.action,
            "target": self.target,
            "decision": self.decision,
            "gate_status": self.gate_status,
            "evidence_status": self.evidence_status,
            "outcome": self.outcome,
            "message": self.message,
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class AgentGateAuditReport:
    status: str
    ledger_source: str
    gate_count: int
    runprint_bundle_count: int
    recorded_event_count: int
    items: tuple[AgentGateAuditItem, ...]
    warnings: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return self.status in {"missing_gate", "blocked", "needs_evidence"}

    def to_dict(self) -> JsonMap:
        return {
            "status": self.status,
            "ledger_source": self.ledger_source,
            "gate_count": self.gate_count,
            "runprint_bundle_count": self.runprint_bundle_count,
            "recorded_event_count": self.recorded_event_count,
            "items": [item.to_dict() for item in self.items],
            "warnings": list(self.warnings),
            "next_action": self.next_action,
        }

    @property
    def next_action(self) -> str:
        if self.items:
            return self.items[0].next_action
        return "Run `delegation agent-gate ... --ledger LEDGER --write` before comparing intent with evidence."


def build_agent_gate_report(
    *,
    agent_id: str,
    action: str,
    target: str,
    manifest: Manifest | None = None,
    manifest_source: str | None = None,
    registry_paths: T.Sequence[Path] = (),
    requested_risk: str | None = None,
    provided_evidence: T.Sequence[str] = (),
    provided_approvals: T.Sequence[str] = (),
) -> AgentGateReport:
    passport_report = build_agent_passport_report(
        manifest=manifest,
        manifest_source=manifest_source,
        registry_paths=registry_paths,
    )
    passport = _find_passport(passport_report.passports, agent_id)
    normalized_action = _clean(action)
    normalized_target = _clean(target)
    evidence = tuple(_dedupe(_clean(item) for item in provided_evidence if _clean(item)))
    approvals = tuple(_dedupe(_clean(item) for item in provided_approvals if _clean(item)))
    risk = _effective_risk(requested_risk, passport, normalized_action, normalized_target)

    checks: list[AgentGateCheck] = []
    if not passport:
        checks.append(
            AgentGateCheck(
                "identity.agent",
                "blocked",
                f"Unknown agent `{agent_id}`.",
                next_action="Register the agent in `agents:` or an Agent Passport registry before gating actions.",
            )
        )
        return AgentGateReport(
            decision="block",
            agent_id=agent_id,
            action=normalized_action,
            target=normalized_target,
            requested_risk=requested_risk,
            effective_risk=risk,
            passport=None,
            checks=tuple(checks),
            provided_approvals=approvals,
            provided_evidence=evidence,
            sources=passport_report.sources,
            registry_warnings=passport_report.warnings,
        )

    action_match = _matching_capability(passport, normalized_action)
    target_match = _matching_target_scope(passport, normalized_target)
    matched_approvals = tuple(
        approval for approval in passport.required_approvals if _approval_matches(normalized_action, approval)
    )
    required_evidence = passport.evidence_requirements
    missing_evidence = tuple(item for item in required_evidence if item not in evidence)
    approval_present = _approval_present(matched_approvals, approvals, normalized_action)

    checks.append(
        AgentGateCheck(
            "identity.agent",
            "passed",
            f"Agent `{passport.id}` is registered from {passport.source}.",
        )
    )
    if passport.warnings:
        checks.append(
            AgentGateCheck(
                "passport.warnings",
                "warning",
                "Passport has warnings: " + "; ".join(passport.warnings),
                next_action="Fix passport warnings before raising autonomy.",
            )
        )
    else:
        checks.append(AgentGateCheck("passport.warnings", "passed", "Passport has no local warnings."))

    if action_match:
        checks.append(
            AgentGateCheck(
                "scope.action",
                "passed",
                f"Action `{normalized_action}` matches capability `{action_match}`.",
            )
        )
    else:
        checks.append(
            AgentGateCheck(
                "scope.action",
                "blocked",
                f"Action `{normalized_action}` is outside this agent passport.",
                next_action="Add a matching capability to this agent passport, or choose an agent that already has it.",
            )
        )

    if target_match:
        checks.append(
            AgentGateCheck(
                "scope.target",
                "passed",
                f"Target `{normalized_target}` matches allowed scope `{target_match}`.",
            )
        )
    else:
        checks.append(
            AgentGateCheck(
                "scope.target",
                "blocked",
                f"Target `{normalized_target}` is outside this agent passport.",
                next_action="Add the target to allowed tools/data/outputs, or choose a narrower target.",
            )
        )

    if risk in {"high", "critical"} and not passport.required_approvals:
        checks.append(
            AgentGateCheck(
                "risk.approval_policy",
                "blocked",
                f"{risk} risk actions need an approval policy, but this passport has none.",
                next_action="Declare required approvals for this agent before high-risk work.",
            )
        )
    else:
        checks.append(
            AgentGateCheck(
                "risk.level",
                "passed",
                f"Effective risk is `{risk}`.",
            )
        )

    if matched_approvals and not approval_present:
        checks.append(
            AgentGateCheck(
                "approval.required",
                "approval_required",
                "Human approval is required for: " + ", ".join(matched_approvals) + ".",
                next_action="Collect approval evidence before live action.",
            )
        )
    elif matched_approvals and approval_present:
        checks.append(
            AgentGateCheck(
                "approval.required",
                "passed",
                "Required approval evidence was provided for: " + ", ".join(matched_approvals) + ".",
            )
        )
    elif risk in {"high", "critical"} and not approvals:
        checks.append(
            AgentGateCheck(
                "approval.risk",
                "approval_required",
                f"{risk} risk work needs human approval even without an exact action match.",
                next_action="Collect explicit human approval before live action.",
            )
        )
    else:
        checks.append(AgentGateCheck("approval.required", "passed", "No approval is required for this action."))

    if required_evidence:
        checks.append(
            AgentGateCheck(
                "evidence.required",
                "passed",
                "Required evidence is declared: " + ", ".join(required_evidence) + ".",
            )
        )
    else:
        checks.append(
            AgentGateCheck(
                "evidence.required",
                "warning",
                "No evidence requirements are declared.",
                next_action="Add evidence requirements so trust can be earned from real proof.",
            )
        )

    return AgentGateReport(
        decision=_decision_from_checks(checks),
        agent_id=agent_id,
        action=normalized_action,
        target=normalized_target,
        requested_risk=requested_risk,
        effective_risk=risk,
        passport=passport,
        checks=tuple(checks),
        required_approvals=passport.required_approvals,
        matched_approvals=matched_approvals,
        provided_approvals=approvals,
        required_evidence=required_evidence,
        provided_evidence=evidence,
        missing_evidence=missing_evidence,
        sources=passport_report.sources,
        registry_warnings=passport_report.warnings,
    )


def build_agent_gate_events(
    report: AgentGateReport,
    *,
    run_id: str,
    start_sequence: int,
    timestamp: str | None = None,
) -> list[LedgerEvent]:
    event_time = timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    action_id = f"agent_gate.{_event_id_part(report.agent_id)}.{_event_id_part(report.action)}"
    return [
        LedgerEvent(
            run_id=run_id,
            sequence=start_sequence,
            timestamp=event_time,
            type="agent.gate.previewed",
            status=report.decision,
            message=f"Agent Gate decision `{report.decision}` for `{report.agent_id}` action `{report.action}`.",
            action_id=action_id,
            details={
                "adapter": "delegation.agent_gate",
                "agent_gate": report.to_dict(),
                "agent_id": report.agent_id,
                "requested_action": report.action,
                "target": report.target,
                "decision": report.decision,
                "effective_risk": report.effective_risk,
                "dry_run": True,
            },
        )
    ]


def build_agent_gate_audit_report(
    ledger_events: T.Sequence[JsonMap],
    *,
    ledger_source: str = "<memory>",
) -> AgentGateAuditReport:
    gate_events = tuple(_agent_gate_events(ledger_events))
    evidence = build_evidence_report(ledger_events, source=ledger_source)
    recorded_events = tuple(_runprint_recorded_events(ledger_events))
    evidence_status = _evidence_status(evidence.bundle_count, len(recorded_events))

    if not gate_events:
        return AgentGateAuditReport(
            status="missing_gate",
            ledger_source=ledger_source,
            gate_count=0,
            runprint_bundle_count=evidence.bundle_count,
            recorded_event_count=len(recorded_events),
            items=(),
            warnings=("No Agent Gate preview events were found in this ledger.",),
        )

    items = tuple(_audit_item(event, evidence_status) for event in gate_events)
    status = _audit_status(items)
    warnings = tuple(evidence.warnings)
    return AgentGateAuditReport(
        status=status,
        ledger_source=ledger_source,
        gate_count=len(gate_events),
        runprint_bundle_count=evidence.bundle_count,
        recorded_event_count=len(recorded_events),
        items=items,
        warnings=warnings,
    )


def render_agent_gate_report(report: AgentGateReport) -> str:
    lines = [
        "Agent Gate",
        "",
        f"Decision: {report.decision}",
        f"Status: {report.status}",
        f"Agent: {report.agent_id}",
    ]
    if report.passport:
        lines.extend(
            [
                f"Name: {report.passport.name}",
                f"Runtime: {report.passport.runtime_type}",
                f"Autonomy: {report.passport.autonomy_level}",
                f"Source: {report.passport.source}",
            ]
        )
    lines.extend(
        [
            f"Action: {report.action}",
            f"Target: {report.target}",
            f"Risk: {report.effective_risk}",
            "",
            "Checks:",
        ]
    )
    for check in report.checks:
        prefix = {
            "passed": "PASS",
            "warning": "WARN",
            "approval_required": "APPROVAL",
            "blocked": "BLOCK",
        }.get(check.status, check.status.upper())
        lines.append(f"- [{prefix}] {check.id}: {check.message}")
        if check.next_action:
            lines.append(f"  next: {check.next_action}")

    lines.extend(["", "Required approvals:"])
    if report.matched_approvals:
        lines.extend(f"- {item}" for item in report.matched_approvals)
    else:
        lines.append("- none")

    lines.extend(["", "Required evidence:"])
    if report.required_evidence:
        lines.extend(f"- {item}" for item in report.required_evidence)
    else:
        lines.append("- none")

    if report.provided_evidence:
        lines.extend(["", "Provided evidence:"])
        lines.extend(f"- {item}" for item in report.provided_evidence)

    lines.extend(["", "Next:", f"- {report.next_action}"])
    return "\n".join(lines)


def render_agent_gate_audit_report(report: AgentGateAuditReport) -> str:
    lines = [
        "Agent Gate Evidence Audit",
        "",
        f"Status: {report.status}",
        f"Ledger: {report.ledger_source}",
        f"Gate previews: {report.gate_count}",
        f"RunPrint planned bundles: {report.runprint_bundle_count}",
        f"RunPrint recorded events: {report.recorded_event_count}",
    ]

    if report.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in report.warnings)

    lines.extend(["", "Intent vs evidence:"])
    if not report.items:
        lines.append("- none")
    for item in report.items:
        lines.append(f"- {item.agent_id} -> {item.action} on {item.target}")
        lines.append(f"  decision: {item.decision}; evidence: {item.evidence_status}; outcome: {item.outcome}")
        lines.append(f"  {item.message}")
        lines.append(f"  next: {item.next_action}")

    lines.extend(["", "Next:", f"- {report.next_action}"])
    return "\n".join(lines)


def _agent_gate_events(events: T.Sequence[JsonMap]) -> T.Iterator[JsonMap]:
    for event in events:
        if event.get("type") == "agent.gate.previewed":
            yield event


def _audit_item(event: JsonMap, evidence_status: str) -> AgentGateAuditItem:
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    gate = details.get("agent_gate") if isinstance(details.get("agent_gate"), dict) else {}
    agent_id = _string_value(gate.get("agent_id") or details.get("agent_id"), default="unknown-agent")
    action = _string_value(gate.get("action") or details.get("requested_action"), default="unknown-action")
    target = _string_value(gate.get("target") or details.get("target"), default="unknown-target")
    decision = _string_value(gate.get("decision") or details.get("decision") or event.get("status"), default="unknown")
    gate_status = _string_value(gate.get("status"), default=_gate_status_for_decision(decision))
    sequence = event.get("sequence") if isinstance(event.get("sequence"), int) else None

    if decision == "block":
        outcome = "blocked_by_gate"
        message = "The gate blocked this intent before execution."
        next_action = "Change the request, agent passport, or target before trying again."
    elif decision == "approval_required":
        outcome = "waiting_for_approval"
        message = "The gate found allowed work, but human approval is still required."
        next_action = "Collect approval evidence, then rerun Agent Gate with `--approval ... --write`."
    elif decision == "warn":
        outcome = "review_warning"
        message = "The gate allowed only a warning-level preview; review before execution."
        next_action = "Resolve warnings or add stronger evidence before raising autonomy."
    elif evidence_status == "recorded":
        outcome = "recorded"
        message = "The gate allowed the intent and RunPrint recorded execution evidence."
        next_action = "Run evals and promotion checks against the ledger."
    elif evidence_status == "planned":
        outcome = "recording_planned"
        message = "The gate allowed the intent and RunPrint has a planned evidence bundle."
        next_action = "Execute under recorder control, then append recorded RunPrint evidence."
    else:
        outcome = "evidence_missing"
        message = "The gate allowed the intent, but no RunPrint evidence plan was found."
        next_action = "Add a `runprint.recorder` step or provide recorded evidence before promotion."

    return AgentGateAuditItem(
        gate_sequence=sequence,
        agent_id=agent_id,
        action=action,
        target=target,
        decision=decision,
        gate_status=gate_status,
        evidence_status=evidence_status,
        outcome=outcome,
        message=message,
        next_action=next_action,
    )


def _audit_status(items: T.Sequence[AgentGateAuditItem]) -> str:
    outcomes = {item.outcome for item in items}
    if "blocked_by_gate" in outcomes:
        return "blocked"
    if "waiting_for_approval" in outcomes:
        return "approval_required"
    if "evidence_missing" in outcomes:
        return "needs_evidence"
    if "review_warning" in outcomes:
        return "warning"
    if "recorded" in outcomes:
        return "recorded"
    return "ready_for_recording"


def _evidence_status(bundle_count: int, recorded_count: int) -> str:
    if recorded_count:
        return "recorded"
    if bundle_count:
        return "planned"
    return "missing"


def _runprint_recorded_events(events: T.Sequence[JsonMap]) -> T.Iterator[JsonMap]:
    for event in events:
        event_type = event.get("type") if isinstance(event.get("type"), str) else ""
        status = event.get("status") if isinstance(event.get("status"), str) else ""
        if not event_type.startswith("runprint.recording."):
            continue
        if event_type.endswith(".planned") or status == "planned":
            continue
        yield event


def _find_passport(passports: T.Sequence[AgentPassport], agent_id: str) -> AgentPassport | None:
    for passport in passports:
        if passport.id == agent_id:
            return passport
    return None


def _effective_risk(requested_risk: str | None, passport: AgentPassport | None, action: str, target: str) -> str:
    risks = [_normalize_risk(requested_risk), _infer_action_risk(action, target)]
    if passport:
        risks.append(_normalize_risk(passport.risk_level))
    return max((risk for risk in risks if risk), key=lambda risk: RISK_RANK[risk], default="medium")


def _infer_action_risk(action: str, target: str) -> str:
    tokens = _tokens(action) | _tokens(target)
    if {"production", "deploy"} & tokens:
        return "critical"
    if {"secret", "delete", "remove", "force"} & tokens:
        return "high"
    if action.startswith(("read.", "summarize.", "classify.", "suggest.", "retrieve.")):
        return "low"
    if WRITE_VERBS & tokens or {"pull", "request", "customer", "crm"} & tokens:
        return "medium"
    return "low"


def _normalize_risk(value: str | None) -> str | None:
    if not value:
        return None
    risk = value.strip().lower()
    return risk if risk in RISK_RANK else None


def _matching_capability(passport: AgentPassport, action: str) -> str | None:
    for capability in passport.capabilities:
        if _action_matches_capability(action, capability):
            return capability
    return None


def _action_matches_capability(action: str, capability: str) -> bool:
    action_norm = _norm(action)
    capability_norm = _norm(capability)
    if not action_norm or not capability_norm:
        return False
    if action_norm == capability_norm:
        return True
    if action_norm.startswith(capability_norm + ".") or capability_norm.startswith(action_norm + "."):
        return True
    action_tokens = _tokens(action)
    capability_tokens = _tokens(capability)
    if len(action_tokens & capability_tokens) >= 2:
        return True
    if "." in action and "." in capability and action.split(".", 1)[0] == capability.split(".", 1)[0]:
        if action.split(".", 1)[0] in GENERIC_CAPABILITY_PREFIXES:
            return False
        return True
    return False


def _matching_target_scope(passport: AgentPassport, target: str) -> str | None:
    scopes = [
        *passport.allowed_data,
        *passport.allowed_tools,
        *passport.expected_outputs,
        *passport.capabilities,
    ]
    for scope in scopes:
        if _target_matches_scope(target, scope):
            return scope
    return None


def _target_matches_scope(target: str, scope: str) -> bool:
    target_norm = _norm(target)
    scope_norm = _norm(scope)
    if not target_norm or not scope_norm:
        return False
    if target_norm == scope_norm:
        return True
    if target_norm == "repository" and (scope_norm == "repository" or "/" in scope or "repository" in scope_norm):
        return True
    if target_norm in {"repo", "working_tree"} and "repository" in scope_norm:
        return True
    if target_norm.startswith(scope_norm + ".") or scope_norm.startswith(target_norm + "."):
        return True
    if target_norm.replace(".", "_") in scope_norm.replace(".", "_"):
        return True
    if len(_tokens(target) & _tokens(scope)) >= 2:
        return True
    return False


def _approval_matches(action: str, approval: str) -> bool:
    action_norm = _norm(action)
    approval_norm = _norm(approval)
    if not action_norm or not approval_norm:
        return False
    if action_norm == approval_norm:
        return True
    action_compact = action_norm.replace(".", "_")
    approval_compact = approval_norm.replace(".", "_")
    if approval_compact in action_compact or action_compact in approval_compact:
        return True
    return bool(_tokens(action) & _tokens(approval)) and len(_tokens(approval) - WRITE_VERBS) > 0


def _approval_present(required: T.Sequence[str], provided: T.Sequence[str], action: str) -> bool:
    if not required:
        return False
    for approval in provided:
        if any(_approval_matches(approval, required_item) for required_item in required):
            return True
        if _approval_matches(action, approval):
            return True
    return False


def _decision_from_checks(checks: T.Sequence[AgentGateCheck]) -> str:
    if any(check.status == "blocked" for check in checks):
        return "block"
    if any(check.status == "approval_required" for check in checks):
        return "approval_required"
    if any(check.status == "warning" for check in checks):
        return "warn"
    return "allow"


def _gate_status_for_decision(decision: str) -> str:
    return {
        "allow": "ready",
        "warn": "warning",
        "approval_required": "approval_required",
        "block": "blocked",
    }.get(decision, "unknown")


def _event_id_part(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    return "_".join(part for part in cleaned.split("_") if part) or "unknown"


def _string_value(value: T.Any, *, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def _tokens(value: str) -> set[str]:
    normalized = _norm(value).replace("/", ".").replace(":", ".").replace("-", ".").replace("_", ".")
    return {item for item in normalized.split(".") if item}


def _norm(value: str) -> str:
    return _clean(value).lower().replace("/", ".").replace(":", ".").replace("-", ".").replace("_", ".")


def _clean(value: str | None) -> str:
    return value.strip() if isinstance(value, str) else ""


def _dedupe(values: T.Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
