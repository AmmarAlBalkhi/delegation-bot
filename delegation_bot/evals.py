#!/usr/bin/env python3
"""Run built-in evals against Delegation Bot ledgers."""

from __future__ import annotations

import json
import typing as T
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from delegation_bot.adapters import get_adapter_contract
from delegation_bot.harness_manifest import Manifest
from delegation_bot.harness_plan import LedgerEvent
from delegation_bot.promotion import JsonMap


class EvalError(ValueError):
    """Raised when eval evidence cannot be read or written."""


@dataclass(frozen=True)
class EvalResult:
    id: str
    status: str
    message: str
    details: JsonMap = field(default_factory=dict)

    def to_dict(self) -> JsonMap:
        return {
            "id": self.id,
            "status": self.status,
            "message": self.message,
            "details": self.details,
        }


def load_jsonl(path: Path) -> list[JsonMap]:
    events: list[JsonMap] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                data = json.loads(line)
                if not isinstance(data, dict):
                    raise EvalError(f"Ledger line {line_number} must be a JSON object")
                events.append(data)
    except OSError as exc:
        raise EvalError(str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise EvalError(f"Ledger JSON error: {exc}") from exc
    return events


def _declared_eval_ids(manifest: Manifest) -> list[str]:
    evals = manifest.get("evals") if isinstance(manifest.get("evals"), list) else []
    ids: list[str] = []
    for index, eval_cfg in enumerate(evals):
        if isinstance(eval_cfg, dict) and isinstance(eval_cfg.get("id"), str):
            ids.append(eval_cfg["id"])
        else:
            ids.append(f"eval_{index + 1}")
    return ids


def _event_type(event: JsonMap) -> str:
    return event.get("type") if isinstance(event.get("type"), str) else ""


def _action_details(event: JsonMap) -> JsonMap:
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    action = details.get("action") if isinstance(details.get("action"), dict) else {}
    return action


def _details(event: JsonMap) -> JsonMap:
    return event.get("details") if isinstance(event.get("details"), dict) else {}


def _is_empty(value: T.Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (dict, list, tuple, set)):
        return not value
    return False


def _adapter_result_records(events: T.Sequence[JsonMap]) -> list[JsonMap]:
    records: dict[tuple[str, str], JsonMap] = {}
    for event in events:
        details = _details(event)
        adapter_result = details.get("adapter_result")
        if not isinstance(adapter_result, dict):
            continue
        adapter = details.get("adapter") or adapter_result.get("adapter_id")
        if not isinstance(adapter, str) or not adapter.strip():
            adapter = "unknown"
        action_id = event.get("action_id") if isinstance(event.get("action_id"), str) else "unknown"
        key = (adapter, action_id)
        record = records.setdefault(
            key,
            {
                "adapter": adapter,
                "action_id": action_id,
                "event_types": [],
                "statuses": [],
                "outputs": {},
                "evidence": {},
            },
        )
        event_type = _event_type(event)
        if event_type:
            record["event_types"].append(event_type)
        status = adapter_result.get("status") or event.get("status")
        if isinstance(status, str) and status.strip():
            record["statuses"].append(status)
        outputs = adapter_result.get("outputs") if isinstance(adapter_result.get("outputs"), dict) else {}
        evidence = adapter_result.get("evidence") if isinstance(adapter_result.get("evidence"), dict) else {}
        record["outputs"].update(outputs)
        record["evidence"].update(evidence)
    return list(records.values())


def eval_ledger_is_valid(events: T.Sequence[JsonMap]) -> EvalResult:
    if not events:
        return EvalResult("ledger_is_valid", "failed", "Ledger is empty.")

    sequences: list[int] = []
    missing_fields: list[str] = []
    required = {"run_id", "sequence", "timestamp", "type", "status", "message", "details"}
    for index, event in enumerate(events, start=1):
        missing = sorted(field for field in required if field not in event)
        if missing:
            missing_fields.append(f"line {index}: {', '.join(missing)}")
        if isinstance(event.get("sequence"), int):
            sequences.append(event["sequence"])

    expected = list(range(1, len(events) + 1))
    if missing_fields:
        return EvalResult(
            "ledger_is_valid",
            "failed",
            "Ledger events are missing required fields.",
            {"missing_fields": missing_fields},
        )
    if sequences != expected:
        return EvalResult(
            "ledger_is_valid",
            "failed",
            "Ledger sequence numbers are not contiguous.",
            {"expected": expected, "actual": sequences},
        )
    return EvalResult("ledger_is_valid", "passed", "Ledger is valid.", {"event_count": len(events)})


def eval_no_duplicate_issue_markers(events: T.Sequence[JsonMap]) -> EvalResult:
    marker_actions: dict[str, set[str]] = {}
    marker_feedback_actions: dict[str, set[str]] = {}
    for event in events:
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        marker = details.get("issue_marker")
        if not isinstance(marker, str):
            adapter_result = details.get("adapter_result") if isinstance(details.get("adapter_result"), dict) else {}
            evidence = adapter_result.get("evidence") if isinstance(adapter_result.get("evidence"), dict) else {}
            marker = evidence.get("issue_marker")
        if isinstance(marker, str):
            action_id = event.get("action_id") if isinstance(event.get("action_id"), str) else "unknown"
            marker_actions.setdefault(marker, set()).add(action_id)
            if _is_feedback_issue_lifecycle(details, marker, action_id):
                marker_feedback_actions.setdefault(marker, set()).add(action_id)

    duplicates = sorted(
        marker
        for marker, action_ids in marker_actions.items()
        if len(action_ids) > 1 and not action_ids <= marker_feedback_actions.get(marker, set())
    )
    if duplicates:
        return EvalResult(
            "no_duplicate_issue_markers",
            "failed",
            "Duplicate issue markers found across multiple actions.",
            {"duplicates": duplicates, "marker_actions": {key: sorted(value) for key, value in marker_actions.items()}},
        )
    return EvalResult(
        "no_duplicate_issue_markers",
        "passed",
        "No duplicate issue markers found.",
        {"marker_count": len(marker_actions)},
    )


def _is_feedback_issue_lifecycle(details: JsonMap, marker: str, action_id: str) -> bool:
    feedback = details.get("feedback") if isinstance(details.get("feedback"), dict) else {}
    if feedback.get("marker") == marker:
        return True
    return marker.startswith("delegation-bot:eval:") and action_id.startswith("feedback.")


def eval_approvals_before_risky_actions(events: T.Sequence[JsonMap]) -> EvalResult:
    approved_action_ids: set[str] = set()
    violations: list[str] = []
    for event in events:
        event_type = _event_type(event)
        action_id = event.get("action_id") if isinstance(event.get("action_id"), str) else None
        if event_type == "approval.granted" and action_id:
            approved_action_ids.add(action_id)
            continue

        if event.get("status") != "executed" or not action_id:
            continue
        action = _action_details(event)
        requires_approval = bool(action.get("requires_approval"))
        risk = action.get("risk") if isinstance(action.get("risk"), str) else "low"
        if (requires_approval or risk == "high") and action_id not in approved_action_ids:
            violations.append(action_id)

    if violations:
        return EvalResult(
            "approvals_before_risky_actions",
            "failed",
            "Risky executed actions are missing approval evidence.",
            {"violations": violations},
        )
    return EvalResult(
        "approvals_before_risky_actions",
        "passed",
        "No risky executed actions were missing approval evidence.",
        {"approved_action_count": len(approved_action_ids)},
    )


def eval_tests_pass_before_pr(events: T.Sequence[JsonMap]) -> EvalResult:
    test_pass_sequences = {
        event.get("sequence")
        for event in events
        if _event_type(event) in {"test.passed", "ci.passed"} and event.get("status") == "passed"
    }
    pr_events = [
        event
        for event in events
        if event.get("status") == "executed" and _event_type(event) in {"github.pull_request.opened", "pr.opened"}
    ]

    if not pr_events:
        return EvalResult(
            "tests_pass_before_pr",
            "blocked",
            "No executed pull request event found; promotion needs real test evidence, not only a dry-run.",
        )

    violations: list[str] = []
    for event in pr_events:
        sequence = event.get("sequence") if isinstance(event.get("sequence"), int) else 0
        if not any(isinstance(test_sequence, int) and test_sequence < sequence for test_sequence in test_pass_sequences):
            action_id = event.get("action_id") if isinstance(event.get("action_id"), str) else str(sequence)
            violations.append(action_id)

    if violations:
        return EvalResult(
            "tests_pass_before_pr",
            "failed",
            "Pull request execution is missing prior passing test evidence.",
            {"violations": violations},
        )
    return EvalResult(
        "tests_pass_before_pr",
        "passed",
        "Every executed pull request had prior passing test evidence.",
        {"pull_request_count": len(pr_events)},
    )


def eval_required_adapter_evidence(events: T.Sequence[JsonMap]) -> EvalResult:
    records = _adapter_result_records(events)
    if not records:
        return EvalResult(
            "required_adapter_evidence",
            "blocked",
            "No SDK-backed adapter result evidence found in the ledger.",
        )

    unknown_contracts: list[JsonMap] = []
    missing_evidence: list[JsonMap] = []
    missing_outputs: list[JsonMap] = []
    blocked_results: list[JsonMap] = []
    failed_results: list[JsonMap] = []

    for record in records:
        adapter = str(record["adapter"])
        action_id = str(record["action_id"])
        statuses = [str(status) for status in record.get("statuses", [])]
        contract = get_adapter_contract(adapter)
        if not contract:
            unknown_contracts.append({"adapter": adapter, "action_id": action_id})
            continue

        evidence = record.get("evidence") if isinstance(record.get("evidence"), dict) else {}
        outputs = record.get("outputs") if isinstance(record.get("outputs"), dict) else {}
        missing_evidence_keys = [
            key
            for key in contract.required_evidence
            if _is_empty(evidence.get(key))
        ]
        missing_output_keys = [
            key
            for key in contract.outputs
            if key != "run_ledger" and _is_empty(outputs.get(key))
        ]

        if missing_evidence_keys:
            missing_evidence.append(
                {
                    "adapter": adapter,
                    "action_id": action_id,
                    "missing": missing_evidence_keys,
                }
            )
        if missing_output_keys:
            missing_outputs.append(
                {
                    "adapter": adapter,
                    "action_id": action_id,
                    "missing": missing_output_keys,
                }
            )

        if any(status == "failed" for status in statuses):
            failed_results.append({"adapter": adapter, "action_id": action_id, "statuses": statuses})
        elif statuses and not any(status in {"planned", "succeeded"} for status in statuses):
            blocked_results.append({"adapter": adapter, "action_id": action_id, "statuses": statuses})

    details = {
        "checked_adapter_results": len(records),
        "unknown_contracts": unknown_contracts,
        "missing_evidence": missing_evidence,
        "missing_outputs": missing_outputs,
        "blocked_results": blocked_results,
        "failed_results": failed_results,
    }
    if unknown_contracts or missing_evidence or missing_outputs or failed_results:
        return EvalResult(
            "required_adapter_evidence",
            "failed",
            "Adapter results are missing required contract evidence or outputs.",
            details,
        )
    if blocked_results:
        return EvalResult(
            "required_adapter_evidence",
            "blocked",
            "One or more adapter results did not reach a planned or succeeded state.",
            details,
        )
    return EvalResult(
        "required_adapter_evidence",
        "passed",
        "All SDK-backed adapter results include required contract evidence and outputs.",
        details,
    )


BUILT_INS: dict[str, T.Callable[[T.Sequence[JsonMap]], EvalResult]] = {
    "ledger_is_valid": eval_ledger_is_valid,
    "no_duplicate_issue_markers": eval_no_duplicate_issue_markers,
    "approvals_before_risky_actions": eval_approvals_before_risky_actions,
    "required_adapter_evidence": eval_required_adapter_evidence,
    "tests_pass_before_pr": eval_tests_pass_before_pr,
}


def run_declared_evals(manifest: Manifest, events: T.Sequence[JsonMap]) -> list[EvalResult]:
    results: list[EvalResult] = [eval_ledger_is_valid(events)]
    for eval_id in _declared_eval_ids(manifest):
        if eval_id == "ledger_is_valid":
            continue
        runner = BUILT_INS.get(eval_id)
        if not runner:
            results.append(EvalResult(eval_id, "blocked", "No built-in runner exists for this eval."))
            continue
        results.append(runner(events))
    return results


def eval_results_to_events(
    results: T.Sequence[EvalResult],
    run_id: str,
    start_sequence: int,
    timestamp: str | None = None,
) -> list[LedgerEvent]:
    event_time = timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    events: list[LedgerEvent] = []
    for offset, result in enumerate(results):
        events.append(
            LedgerEvent(
                run_id=run_id,
                sequence=start_sequence + offset,
                timestamp=event_time,
                type="eval.result",
                status=result.status,
                message=result.message,
                details={"eval_id": result.id, "eval": result.to_dict()},
            )
        )
    return events


def append_jsonl(events: T.Iterable[LedgerEvent], path: Path) -> None:
    try:
        with path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")
    except OSError as exc:
        raise EvalError(str(exc)) from exc


def render_eval_report(results: T.Sequence[EvalResult]) -> str:
    lines = ["Eval report", ""]
    for result in results:
        lines.append(f"- {result.id}: {result.status}")
        lines.append(f"  {result.message}")
    return "\n".join(lines)
