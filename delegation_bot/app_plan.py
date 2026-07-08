#!/usr/bin/env python3
"""Plan the first visible DelegationHQ EXE app experience."""

from __future__ import annotations

import typing as T
from dataclasses import dataclass


JsonMap = dict[str, T.Any]


@dataclass(frozen=True)
class AppSurface:
    id: str
    title: str
    purpose: str
    source: str
    first_slice: str
    live_risk: str = "none"

    def to_dict(self) -> JsonMap:
        return {
            "id": self.id,
            "title": self.title,
            "purpose": self.purpose,
            "source": self.source,
            "first_slice": self.first_slice,
            "live_risk": self.live_risk,
        }


@dataclass(frozen=True)
class AppPlan:
    status: str
    app_name: str
    mode: str
    promise: str
    next_design_decision: str
    surfaces: tuple[AppSurface, ...]
    guardrails: tuple[str, ...]
    milestones: tuple[str, ...]
    bring_your_own_agent: JsonMap

    def to_dict(self) -> JsonMap:
        return {
            "status": self.status,
            "app_name": self.app_name,
            "mode": self.mode,
            "promise": self.promise,
            "next_design_decision": self.next_design_decision,
            "surfaces": [surface.to_dict() for surface in self.surfaces],
            "guardrails": list(self.guardrails),
            "milestones": list(self.milestones),
            "bring_your_own_agent": self.bring_your_own_agent,
        }


def build_app_plan() -> AppPlan:
    """Return the current app plan without creating windows or live side effects."""

    return AppPlan(
        status="planning",
        app_name="DelegationHQ Local Mission Cockpit",
        mode="local-first Windows EXE",
        promise="Open one app, see the mission, inspect proof, and keep risky actions gated.",
        next_design_decision=(
            "Choose the visual direction before building the actual interface: futuristic cockpit, "
            "quiet operator console, or another approved style."
        ),
        surfaces=(
            AppSurface(
                id="first_run",
                title="First Run",
                purpose="Let a new user run demo, doctor, and init without learning Python.",
                source="delegation demo; delegation doctor; delegation init",
                first_slice="Buttons or commands for demo, readiness, and starter Harnessfile creation.",
            ),
            AppSurface(
                id="mission_snapshot",
                title="Mission Snapshot",
                purpose="Show the current Harnessfile, ledger status, next safe action, evals, and adapters.",
                source="delegation dashboard --json",
                first_slice="Read-only mission summary over a local ledger.",
            ),
            AppSurface(
                id="evidence",
                title="Evidence",
                purpose="Show planned proof bundles from recorder, monitor, test, and workflow evidence tools.",
                source="delegation evidence --json",
                first_slice="Evidence bundle cards from ledger data, with RunPrint as the first recorder adapter.",
            ),
            AppSurface(
                id="agent_passports",
                title="Agent Passports",
                purpose="Register Bring Your Own Agent runtimes under DelegationHQ control.",
                source="Harnessfile agents and future Agent Contract registry",
                first_slice="Read-only list of agents, runtime type, capabilities, risk, and promotion evals.",
            ),
            AppSurface(
                id="approval_inbox",
                title="Approval Inbox",
                purpose="Make risky actions visible before live writes, workflow dispatch, or agent execution.",
                source="agent-gate; policy gates; apply-issues/apply-actions previews",
                first_slice="Preview-only approval queue; no live action button until gates and confirmations exist.",
                live_risk="high",
            ),
        ),
        guardrails=(
            "The first app slice is read-only by default.",
            "No model calls happen unless the user explicitly opts in.",
            "No GitHub writes, workflow dispatches, or agent execution happen from the app without exact confirmations.",
            "The UI consumes existing JSON reports before inventing new state.",
            "Visual/interface design waits for maintainer approval.",
        ),
        milestones=(
            "M1: EXE opens a local command-backed cockpit plan and runs demo/doctor safely.",
            "M2: EXE reads a ledger and renders mission snapshot plus evidence bundle data.",
            "M3: EXE lists Agent Passports for built-in and custom agents.",
            "M4: EXE previews approval gates for issues, workflows, and BYOA agents.",
            "M5: EXE packages cleanly with checksums, release rehearsal evidence, and install smoke tests.",
        ),
        bring_your_own_agent={
            "principle": "DelegationHQ is the control layer above any agent, not one agent.",
            "passport_fields": [
                "agent id/name",
                "runtime type",
                "command/API/webhook/MCP endpoint",
                "capabilities",
                "allowed tools/data",
                "risk level",
                "required approvals",
                "expected outputs",
                "evidence requirements",
                "evals required for promotion",
            ],
            "examples": [
                "LangGraph agent",
                "CRM/RAG agent",
                "coding agent",
                "CLI agent",
                "MCP workflow",
                "API/webhook agent",
                "local tool",
            ],
        },
    )


def render_app_plan(plan: AppPlan) -> str:
    lines = [
        "DelegationHQ EXE App Plan",
        "",
        f"Status: {plan.status}",
        f"App: {plan.app_name}",
        f"Mode: {plan.mode}",
        f"Promise: {plan.promise}",
        f"Design decision: {plan.next_design_decision}",
        "",
        "First surfaces:",
    ]
    for surface in plan.surfaces:
        lines.append(f"- {surface.title} ({surface.id})")
        lines.append(f"  purpose: {surface.purpose}")
        lines.append(f"  source: {surface.source}")
        lines.append(f"  first slice: {surface.first_slice}")
        if surface.live_risk != "none":
            lines.append(f"  live risk: {surface.live_risk}")

    lines.extend(["", "Guardrails:"])
    lines.extend(f"- {item}" for item in plan.guardrails)

    lines.extend(["", "Milestones:"])
    lines.extend(f"- {item}" for item in plan.milestones)

    byoa = plan.bring_your_own_agent
    lines.extend(["", "Bring Your Own Agent:"])
    lines.append(f"- principle: {byoa['principle']}")
    lines.append("- passport fields: " + ", ".join(str(item) for item in byoa["passport_fields"]))
    lines.append("- examples: " + ", ".join(str(item) for item in byoa["examples"]))
    return "\n".join(lines)
