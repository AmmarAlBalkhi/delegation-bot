#!/usr/bin/env python3
"""Generate compact adapter-result ledger fixtures."""

from __future__ import annotations

import argparse
import json
import sys
import typing as T
from dataclasses import replace
from pathlib import Path

from delegation_bot.adapter_sdk import (
    AdapterEvent,
    AdapterRequest,
    AdapterResult,
    validate_adapter_result,
)
from delegation_bot.builtin_adapters import get_builtin_adapter, list_builtin_adapters


JsonMap = dict[str, T.Any]
FIXTURE_TIMESTAMP = "2026-07-04T08:00:00+00:00"
FIXTURE_STATES = ("good", "blocked", "failed")


SAMPLE_INPUTS: dict[str, JsonMap] = {
    "github.issue": {
        "repository": "AmmarAlBalkhi/delegation-bot",
        "issue_title": "Fixture issue",
        "issue_body": "Fixture issue body.",
    },
    "github.actions": {
        "repository": "AmmarAlBalkhi/delegation-bot",
        "workflow_ref": ".github/workflows/tests.yml",
    },
    "sample.echo": {
        "label": "fixture",
        "message": "Fixture adapter evidence.",
    },
    "mcp.tool": {
        "server": "local-repository-tools",
        "tool_name": "inspect_repository",
        "arguments": {"path": ".", "mode": "dry_run"},
    },
    "openai.agents": {
        "model": "gpt-5.5",
        "tools": ["github.issue", "mcp.tool"],
        "instructions": "Draft a safe delegation plan.",
    },
    "anthropic.messages": {
        "model": "claude-sonnet",
        "system_prompt": "Review the plan.",
        "messages": [{"role": "user", "content": "Review this Harnessfile."}],
    },
    "codex.thread": {
        "objective": "Draft a scoped code change.",
        "repository": "AmmarAlBalkhi/delegation-bot",
        "allowed_files": ["delegation_bot/**", "tests/**"],
    },
    "claude.code": {
        "objective": "Review proposed code changes.",
        "repository": "AmmarAlBalkhi/delegation-bot",
        "allowed_files": ["delegation_bot/**", "tests/**"],
    },
    "local.classifier": {
        "plan": "Classify this dry-run mission for risk.",
        "policy": "Require approvals for writes, workflows, and agent execution.",
    },
}


class FixtureError(ValueError):
    """Raised when a fixture cannot be generated."""


def adapter_slug(adapter_id: str) -> str:
    return adapter_id.replace(".", "-")


def sample_inputs_for_adapter(adapter_id: str) -> JsonMap:
    adapter = get_builtin_adapter(adapter_id)
    if not adapter:
        raise FixtureError(f"No SDK-backed dry-run adapter found for `{adapter_id}`.")

    inputs = dict(SAMPLE_INPUTS.get(adapter_id, {}))
    for input_name in adapter.contract.inputs:
        inputs.setdefault(input_name, f"fixture-{input_name}")
    return inputs


def fixture_inputs_for_state(adapter_id: str, state: str) -> JsonMap:
    if state not in FIXTURE_STATES:
        raise FixtureError(f"Unknown fixture state `{state}`.")

    adapter = get_builtin_adapter(adapter_id)
    if not adapter:
        raise FixtureError(f"No SDK-backed dry-run adapter found for `{adapter_id}`.")

    inputs = sample_inputs_for_adapter(adapter_id)
    if state == "blocked" and adapter.contract.inputs:
        inputs[adapter.contract.inputs[0]] = ""
    return inputs


def adapter_request_for_fixture(adapter_id: str, state: str) -> AdapterRequest:
    slug = adapter_slug(adapter_id)
    return AdapterRequest(
        adapter_id=adapter_id,
        action_id=f"executor.{adapter_id.replace('.', '_')}",
        mission_id=f"fixture-{slug}-{state}",
        objective=f"Generate a {state} fixture for {adapter_id}.",
        inputs=fixture_inputs_for_state(adapter_id, state),
        dry_run=True,
    )


def _failed_result(result: AdapterResult) -> AdapterResult:
    failed_events = tuple(
        replace(
            event,
            status="failed",
            message=f"Fixture forced failed adapter event `{event.type}`.",
        )
        for event in result.ledger_events
    )
    return replace(
        result,
        status="failed",
        message=f"Fixture forced failed adapter result for `{result.action_id}`.",
        ledger_events=failed_events,
    )


def adapter_result_for_fixture(adapter_id: str, state: str) -> AdapterResult:
    adapter = get_builtin_adapter(adapter_id)
    if not adapter:
        raise FixtureError(f"No SDK-backed dry-run adapter found for `{adapter_id}`.")

    result = adapter.plan(adapter_request_for_fixture(adapter_id, state))
    if state == "failed":
        result = _failed_result(result)

    errors = validate_adapter_result(adapter.contract, result)
    if errors:
        raise FixtureError("; ".join(errors))
    return result


def _result_payload(result: AdapterResult) -> JsonMap:
    return {
        "status": result.status,
        "message": result.message,
        "outputs": result.outputs,
        "evidence": result.evidence,
        "dry_run": result.dry_run,
    }


def _event(
    run_id: str,
    sequence: int,
    event_type: str,
    status: str,
    message: str,
    action_id: str | None = None,
    details: JsonMap | None = None,
) -> JsonMap:
    return {
        "run_id": run_id,
        "sequence": sequence,
        "timestamp": FIXTURE_TIMESTAMP,
        "type": event_type,
        "status": status,
        "message": message,
        "action_id": action_id,
        "details": details or {},
    }


def build_adapter_fixture(adapter_id: str, state: str) -> list[JsonMap]:
    adapter = get_builtin_adapter(adapter_id)
    if not adapter:
        raise FixtureError(f"No SDK-backed dry-run adapter found for `{adapter_id}`.")

    result = adapter_result_for_fixture(adapter_id, state)
    run_id = f"fixture-{adapter_slug(adapter_id)}-{state}"
    action_id = result.action_id
    action_type = f"adapter.{adapter_id}.prepare"
    events = [
        _event(
            run_id=run_id,
            sequence=1,
            event_type="plan.compiled",
            status="planned",
            message="Compiled fixture plan.",
        ),
        _event(
            run_id=run_id,
            sequence=2,
            event_type=f"dry_run.{action_type}",
            status="planned",
            message=f"Prepare {adapter_id} adapter.",
            action_id=action_id,
            details={
                "action": {
                    "id": action_id,
                    "type": action_type,
                    "adapter": adapter_id,
                    "risk": adapter.contract.risk,
                    "requires_approval": bool(adapter.contract.approval_required_for),
                }
            },
        ),
    ]
    for adapter_event in result.ledger_events:
        details = dict(adapter_event.details)
        details["adapter_result"] = _result_payload(result)
        events.append(
            _event(
                run_id=run_id,
                sequence=len(events) + 1,
                event_type=adapter_event.type,
                status=adapter_event.status,
                message=adapter_event.message,
                action_id=adapter_event.action_id or action_id,
                details=details,
            )
        )
    return events


def write_jsonl(events: T.Iterable[JsonMap], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True) + "\n")


def fixture_filename(adapter_id: str, state: str) -> str:
    return f"adapter-{adapter_slug(adapter_id)}-{state}.jsonl"


def generate_all(output_dir: Path) -> list[Path]:
    written: list[Path] = []
    for adapter in list_builtin_adapters():
        for state in FIXTURE_STATES:
            path = output_dir / fixture_filename(adapter.contract.id, state)
            write_jsonl(build_adapter_fixture(adapter.contract.id, state), path)
            written.append(path)
    return written


def main(argv: T.Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("adapter_id", nargs="?", default="sample.echo")
    parser.add_argument("--state", choices=FIXTURE_STATES, default="good")
    parser.add_argument("--output", help="Write one fixture to this JSONL path.")
    parser.add_argument("--all", action="store_true", help="Generate fixtures for every SDK-backed adapter.")
    parser.add_argument(
        "--output-dir",
        default="examples/ledgers/generated",
        help="Directory used with --all.",
    )
    args = parser.parse_args(argv)

    try:
        if args.all:
            paths = generate_all(Path(args.output_dir))
            for path in paths:
                print(path)
            return 0

        events = build_adapter_fixture(args.adapter_id, args.state)
        if args.output:
            write_jsonl(events, Path(args.output))
            print(args.output)
        else:
            for event in events:
                print(json.dumps(event, sort_keys=True))
        return 0
    except FixtureError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
