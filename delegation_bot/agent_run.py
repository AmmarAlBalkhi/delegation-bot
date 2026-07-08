#!/usr/bin/env python3
"""Controlled local agent execution under Agent Gate."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
import typing as T
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from delegation_bot.agent_gate import AgentGateReport, build_agent_gate_events, build_agent_gate_report
from delegation_bot.evals import append_jsonl, load_jsonl
from delegation_bot.harness_manifest import Manifest
from delegation_bot.harness_plan import LedgerEvent


JsonMap = dict[str, T.Any]
LOCAL_AGENT_EXECUTION_CONFIRMATION = "LOCAL_AGENT_EXECUTION"
AGENT_RUN_SCHEMA_VERSION = "delegation.agent-run.v1"
DEFAULT_TIMEOUT_SECONDS = 60
MAX_CAPTURE_CHARS = 12000


@dataclass(frozen=True)
class AgentRunReport:
    status: str
    ledger: str
    agent_id: str
    action: str
    target: str
    action_id: str
    gate: AgentGateReport
    command: str | None
    cwd: str
    executed: bool
    output_artifact: str | None = None
    returncode: int | None = None
    duration_seconds: float | None = None
    timed_out: bool = False
    stdout_tail: str = ""
    stderr_tail: str = ""
    event_count: int = 0

    @property
    def blocked(self) -> bool:
        return self.status in {"blocked", "approval_required", "failed", "timed_out", "not_executable"}

    def to_dict(self) -> JsonMap:
        return {
            "schema_version": AGENT_RUN_SCHEMA_VERSION,
            "status": self.status,
            "ledger": self.ledger,
            "agent_id": self.agent_id,
            "action": self.action,
            "target": self.target,
            "action_id": self.action_id,
            "gate": self.gate.to_dict(),
            "command": self.command,
            "cwd": self.cwd,
            "executed": self.executed,
            "output_artifact": self.output_artifact,
            "returncode": self.returncode,
            "duration_seconds": self.duration_seconds,
            "timed_out": self.timed_out,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "event_count": self.event_count,
            "next_actions": list(self.next_actions),
        }

    @property
    def next_actions(self) -> tuple[str, ...]:
        if self.status == "previewed":
            return (
                (
                    f"delegation agent-run {self.agent_id} --ledger {self.ledger} --action {self.action} "
                    f"--target {self.target} --execute --confirm {LOCAL_AGENT_EXECUTION_CONFIRMATION}"
                ),
                "Review the gate receipt before execution.",
            )
        if self.status == "recorded":
            return (
                f"delegation agent-audit --ledger {self.ledger}",
                f"delegation mission-status --ledger {self.ledger}",
            )
        if self.status == "approval_required":
            return ("Collect approval evidence, then rerun agent-run with --approval.",)
        if self.status == "not_executable":
            return ("Register a command-backed agent with `delegation agent-add --command ...`.",)
        return (self.gate.next_action,)


def run_agent_under_control(
    *,
    agent_id: str,
    action: str,
    target: str,
    ledger_path: Path,
    registry_paths: T.Sequence[Path] = (),
    manifest: Manifest | None = None,
    manifest_source: str | None = None,
    requested_risk: str | None = None,
    approvals: T.Sequence[str] = (),
    evidence: T.Sequence[str] = (),
    execute: bool = False,
    confirm: str | None = None,
    cwd: Path | None = None,
    output_dir: Path | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> AgentRunReport:
    if execute and confirm != LOCAL_AGENT_EXECUTION_CONFIRMATION:
        raise ValueError(f"--execute requires --confirm {LOCAL_AGENT_EXECUTION_CONFIRMATION}")

    ledger = ledger_path.resolve()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    existing_events = load_jsonl(ledger) if ledger.exists() else []
    run_id = _run_id(existing_events) or f"agent-run-{_event_id_part(agent_id)}"
    start_sequence = len(existing_events) + 1
    gate = build_agent_gate_report(
        agent_id=agent_id,
        action=action,
        target=target,
        manifest=manifest,
        manifest_source=manifest_source,
        registry_paths=registry_paths,
        requested_risk=requested_risk,
        provided_evidence=evidence,
        provided_approvals=approvals,
    )
    gate_events = build_agent_gate_events(gate, run_id=run_id, start_sequence=start_sequence)
    action_id = gate_events[0].action_id or f"agent_gate.{_event_id_part(agent_id)}.{_event_id_part(action)}"
    command = _command_from_gate(gate)
    workdir = (cwd or Path.cwd()).resolve()

    if not execute:
        append_jsonl(gate_events, ledger)
        return AgentRunReport(
            status="previewed" if gate.decision != "block" else "blocked",
            ledger=str(ledger),
            agent_id=agent_id,
            action=gate.action,
            target=gate.target,
            action_id=action_id,
            gate=gate,
            command=command,
            cwd=str(workdir),
            executed=False,
            event_count=len(gate_events),
        )

    if gate.decision != "allow":
        append_jsonl(gate_events, ledger)
        return AgentRunReport(
            status=gate.decision,
            ledger=str(ledger),
            agent_id=agent_id,
            action=gate.action,
            target=gate.target,
            action_id=action_id,
            gate=gate,
            command=command,
            cwd=str(workdir),
            executed=False,
            event_count=len(gate_events),
        )

    if not command:
        append_jsonl(gate_events, ledger)
        return AgentRunReport(
            status="not_executable",
            ledger=str(ledger),
            agent_id=agent_id,
            action=gate.action,
            target=gate.target,
            action_id=action_id,
            gate=gate,
            command=None,
            cwd=str(workdir),
            executed=False,
            event_count=len(gate_events),
        )

    events: list[LedgerEvent] = list(gate_events)
    timestamp = _now()
    events.append(
        LedgerEvent(
            run_id=run_id,
            sequence=start_sequence + len(events),
            timestamp=timestamp,
            type="agent.execution.started",
            status="running",
            message=f"Command-backed agent `{agent_id}` started under Agent Gate.",
            action_id=action_id,
            details={
                "schema_version": AGENT_RUN_SCHEMA_VERSION,
                "agent_id": agent_id,
                "command": command,
                "cwd": str(workdir),
                "timeout_seconds": timeout_seconds,
                "gate_decision": gate.decision,
            },
        )
    )
    execution = _execute_command(command, cwd=workdir, timeout_seconds=timeout_seconds)
    artifact_path = _write_execution_artifact(
        output_dir=(output_dir.resolve() if output_dir else ledger.parent / "agent-runs"),
        action_id=action_id,
        agent_id=agent_id,
        command=command,
        cwd=workdir,
        execution=execution,
    )
    completed_status = _completion_status(execution)
    events.append(
        LedgerEvent(
            run_id=run_id,
            sequence=start_sequence + len(events),
            timestamp=_now(),
            type="agent.execution.completed" if completed_status == "completed" else "agent.execution.failed",
            status=completed_status,
            message=f"Command-backed agent `{agent_id}` finished with status `{completed_status}`.",
            action_id=action_id,
            details={
                "schema_version": AGENT_RUN_SCHEMA_VERSION,
                "agent_id": agent_id,
                "command": command,
                "cwd": str(workdir),
                "returncode": execution["returncode"],
                "duration_seconds": execution["duration_seconds"],
                "timed_out": execution["timed_out"],
                "stdout_tail": _tail(execution["stdout"]),
                "stderr_tail": _tail(execution["stderr"]),
                "output_artifact": str(artifact_path),
            },
        )
    )
    events.append(
        LedgerEvent(
            run_id=run_id,
            sequence=start_sequence + len(events),
            timestamp=_now(),
            type="runprint.recording.completed",
            status="completed",
            message=f"Local RunPrint-style evidence recorded for `{action_id}`.",
            action_id=action_id,
            details={
                "schema_version": "delegation.runprint-ingest.v1",
                "adapter": "runprint.local_agent_run",
                "recorder": "runprint",
                "target_action_id": action_id,
                "recording_id": f"local-{_event_id_part(action_id)}",
                "evidence_bundle_id": f"bundle-{_event_id_part(action_id)}",
                "artifact_manifest": [
                    {
                        "id": "command-output",
                        "kind": "json",
                        "path": str(artifact_path),
                        "required": True,
                    }
                ],
                "artifact_count": 1,
                "summary": "Command output, exit code, duration, and gate receipt were recorded locally.",
                "source": "delegation agent-run",
                "ingested": True,
                "capture_mode": "local-command",
            },
        )
    )
    append_jsonl(events, ledger)
    return AgentRunReport(
        status="recorded" if completed_status == "completed" else completed_status,
        ledger=str(ledger),
        agent_id=agent_id,
        action=gate.action,
        target=gate.target,
        action_id=action_id,
        gate=gate,
        command=command,
        cwd=str(workdir),
        executed=True,
        output_artifact=str(artifact_path),
        returncode=execution["returncode"],
        duration_seconds=execution["duration_seconds"],
        timed_out=execution["timed_out"],
        stdout_tail=_tail(execution["stdout"]),
        stderr_tail=_tail(execution["stderr"]),
        event_count=len(events),
    )


def render_agent_run_report(report: AgentRunReport) -> str:
    lines = [
        "Agent Run",
        "",
        f"Status: {report.status}",
        f"Ledger: {report.ledger}",
        f"Agent: {report.agent_id}",
        f"Action: {report.action}",
        f"Target: {report.target}",
        f"Gate: {report.gate.decision}",
        f"Executed: {str(report.executed).lower()}",
    ]
    if report.command:
        lines.append(f"Command: {report.command}")
    if report.returncode is not None:
        lines.append(f"Exit code: {report.returncode}")
    if report.duration_seconds is not None:
        lines.append(f"Duration: {report.duration_seconds:.3f}s")
    if report.output_artifact:
        lines.append(f"Evidence: {report.output_artifact}")
    if report.stdout_tail:
        lines.extend(["", "Stdout:", report.stdout_tail])
    if report.stderr_tail:
        lines.extend(["", "Stderr:", report.stderr_tail])
    lines.extend(
        [
            "",
            "Plain language:",
            "- DelegationHQ checked the agent passport first.",
            "- The command ran only after the exact confirmation token.",
            "- Output and exit code were recorded into ledger evidence.",
            "",
            "Next:",
        ]
    )
    lines.extend(f"- {action}" for action in report.next_actions)
    return "\n".join(lines)


def _execute_command(command: str, *, cwd: Path, timeout_seconds: int) -> JsonMap:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            _split_command(command),
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        duration = time.monotonic() - started
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout or "",
            "stderr": completed.stderr or "",
            "duration_seconds": round(duration, 3),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - started
        return {
            "returncode": None,
            "stdout": _decode_timeout_output(exc.stdout),
            "stderr": _decode_timeout_output(exc.stderr),
            "duration_seconds": round(duration, 3),
            "timed_out": True,
        }


def _write_execution_artifact(
    *,
    output_dir: Path,
    action_id: str,
    agent_id: str,
    command: str,
    cwd: Path,
    execution: JsonMap,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{_event_id_part(action_id)}.json"
    payload = {
        "schema_version": AGENT_RUN_SCHEMA_VERSION,
        "agent_id": agent_id,
        "action_id": action_id,
        "command": command,
        "cwd": str(cwd),
        "returncode": execution["returncode"],
        "duration_seconds": execution["duration_seconds"],
        "timed_out": execution["timed_out"],
        "stdout": execution["stdout"],
        "stderr": execution["stderr"],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _command_from_gate(gate: AgentGateReport) -> str | None:
    if not gate.passport:
        return None
    endpoint = gate.passport.endpoint
    if endpoint.get("type") != "command":
        return None
    value = endpoint.get("value")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _split_command(command: str) -> list[str]:
    parts = shlex.split(command, posix=(os.name != "nt"))
    return [_strip_outer_quotes(part) for part in parts]


def _strip_outer_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _completion_status(execution: JsonMap) -> str:
    if execution["timed_out"]:
        return "timed_out"
    return "completed" if execution["returncode"] == 0 else "failed"


def _tail(value: T.Any) -> str:
    text = value if isinstance(value, str) else ""
    if len(text) <= MAX_CAPTURE_CHARS:
        return text.strip()
    return text[-MAX_CAPTURE_CHARS:].strip()


def _decode_timeout_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _run_id(events: T.Sequence[JsonMap]) -> str | None:
    if not events:
        return None
    value = events[0].get("run_id")
    return value if isinstance(value, str) and value.strip() else None


def _event_id_part(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    return "_".join(part for part in cleaned.split("_") if part) or "unknown"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
