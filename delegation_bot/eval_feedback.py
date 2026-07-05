#!/usr/bin/env python3
"""Turn failed eval ledger evidence into dry-run GitHub Issue drafts."""

from __future__ import annotations

import hashlib
import json
import typing as T
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from delegation_bot.adapter_sdk import AdapterRequest, AdapterResult, validate_adapter_result
from delegation_bot.builtin_adapters import get_builtin_adapter
from delegation_bot.evals import EvalResult
from delegation_bot.harness_manifest import Manifest
from delegation_bot.harness_plan import LedgerEvent


JsonMap = dict[str, T.Any]
SECRET_KEY_PARTS = ("token", "secret", "password", "api_key", "authorization", "credential")
DEFAULT_BLOCKED_REPEAT_THRESHOLD = 2


@dataclass(frozen=True)
class FeedbackIssueDraft:
    eval_id: str
    status: str
    marker: str
    title: str
    body: str
    adapter_result: AdapterResult
    operation: str = "create"
    occurrence_count: int = 1
    existing_feedback_events: int = 0
    source_event: JsonMap = field(default_factory=dict)

    def to_dict(self) -> JsonMap:
        return {
            "eval_id": self.eval_id,
            "status": self.status,
            "marker": self.marker,
            "title": self.title,
            "body": self.body,
            "adapter_result": self.adapter_result.to_dict(),
            "operation": self.operation,
            "occurrence_count": self.occurrence_count,
            "existing_feedback_events": self.existing_feedback_events,
            "source_event": self.source_event,
        }


def default_repository(manifest: Manifest) -> str:
    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
    permissions = policies.get("permissions") if isinstance(policies, dict) else {}
    repositories = permissions.get("allowed_repositories") if isinstance(permissions, dict) else []
    if isinstance(repositories, list) and repositories and isinstance(repositories[0], str):
        return repositories[0]
    owners = manifest.get("owners") if isinstance(manifest.get("owners"), dict) else {}
    owner = owners.get("accountable") if isinstance(owners, dict) else None
    return f"{owner}/delegation-bot" if isinstance(owner, str) and owner.strip() else "owner/repo"


def sanitize_details(value: T.Any) -> T.Any:
    if isinstance(value, dict):
        sanitized: JsonMap = {}
        for key, item in value.items():
            key_text = str(key)
            if any(part in key_text.lower() for part in SECRET_KEY_PARTS):
                sanitized[key_text] = "[redacted]"
            else:
                sanitized[key_text] = sanitize_details(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_details(item) for item in value]
    if isinstance(value, str) and len(value) > 1000:
        return value[:1000] + "...[truncated]"
    return value


def _json_dumps(value: T.Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def eval_issue_marker(repository: str, harness_id: str, eval_id: str, details: JsonMap) -> str:
    normalized = json.dumps(
        {
            "repository": repository,
            "harness_id": harness_id,
            "eval_id": eval_id,
            "details": sanitize_details(details),
        },
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"delegation-bot:eval:{eval_id}:{digest}"


def _eval_event_payload(event: JsonMap) -> tuple[str, str, str, JsonMap]:
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    eval_payload = details.get("eval") if isinstance(details.get("eval"), dict) else {}
    eval_id = details.get("eval_id") if isinstance(details.get("eval_id"), str) else str(eval_payload.get("id", "unknown_eval"))
    status = event.get("status") if isinstance(event.get("status"), str) else str(eval_payload.get("status", "unknown"))
    message = event.get("message") if isinstance(event.get("message"), str) else str(eval_payload.get("message", ""))
    eval_details = eval_payload.get("details") if isinstance(eval_payload.get("details"), dict) else {}
    return eval_id, status, message, eval_details


def is_feedback_candidate(event: JsonMap, include_blocked: bool = False) -> bool:
    if event.get("type") != "eval.result":
        return False
    statuses = {"failed"}
    if include_blocked:
        statuses.add("blocked")
    return event.get("status") in statuses


def issue_body_for_eval(
    *,
    marker: str,
    message: str,
    event: JsonMap,
    eval_details: JsonMap,
    ledger_source: str,
    operation: str = "create",
    occurrence_count: int = 1,
    existing_feedback_events: int = 0,
) -> str:
    sanitized = sanitize_details(eval_details)
    run_id = event.get("run_id", "unknown")
    sequence = event.get("sequence", "unknown")
    status = event.get("status", "unknown")
    return "\n".join(
        [
            f"<!-- {marker} -->",
            "",
            "## What Failed",
            "",
            message or "Eval reported a failed or blocked state.",
            "",
            "## Ledger Evidence",
            "",
            f"- run_id: `{run_id}`",
            f"- sequence: `{sequence}`",
            f"- status: `{status}`",
            f"- source ledger: `{ledger_source}`",
            "",
            "## Repeat Signal",
            "",
            f"- planned operation: `{operation}`",
            f"- matching eval occurrences in this ledger: `{occurrence_count}`",
            f"- existing feedback events in this ledger: `{existing_feedback_events}`",
            "",
            "## Failure Details",
            "",
            "```json",
            _json_dumps(sanitized),
            "```",
            "",
            "## Suggested Fix",
            "",
            "- [ ] decide whether this is a product bug, docs gap, adapter gap, or playbook gap",
            "- [ ] add or update a regression eval",
            "- [ ] update the affected adapter, playbook, policy, or documentation",
            "- [ ] rerun `python scripts/qa.py`",
        ]
    )


def build_feedback_issue_draft(
    manifest: Manifest,
    event: JsonMap,
    *,
    repository: str,
    ledger_source: str,
    occurrence_count: int = 1,
    existing_feedback_events: int = 0,
) -> FeedbackIssueDraft:
    adapter = get_builtin_adapter("github.issue")
    if not adapter:
        raise LookupError("github.issue dry-run adapter is required for feedback drafts")

    eval_id, status, message, eval_details = _eval_event_payload(event)
    harness_id = str(manifest.get("id", "unknown-harness"))
    marker = eval_issue_marker(repository, harness_id, eval_id, eval_details)
    issue_status = "failed" if status == "failed" else "blocked"
    operation = "update" if occurrence_count > 1 or existing_feedback_events else "create"
    title_prefix = "Update eval" if operation == "update" else "Eval"
    title = f"{title_prefix} {issue_status}: {eval_id}"
    body = issue_body_for_eval(
        marker=marker,
        message=message,
        event=event,
        eval_details=eval_details,
        ledger_source=ledger_source,
        operation=operation,
        occurrence_count=occurrence_count,
        existing_feedback_events=existing_feedback_events,
    )
    request = AdapterRequest(
        adapter_id="github.issue",
        action_id=f"feedback.{operation}.{eval_id}.{marker.rsplit(':', 1)[-1]}",
        mission_id=harness_id,
        objective=f"Create or update dry-run feedback issue for eval `{eval_id}`.",
        inputs={
            "repository": repository,
            "issue_title": title,
            "issue_body": body,
        },
    )
    result = adapter.plan(request)
    errors = validate_adapter_result(adapter.contract, result)
    if errors:
        raise ValueError("; ".join(errors))
    return FeedbackIssueDraft(
        eval_id=eval_id,
        status=status,
        marker=marker,
        title=title,
        body=body,
        adapter_result=result,
        operation=operation,
        occurrence_count=occurrence_count,
        existing_feedback_events=existing_feedback_events,
        source_event=event,
    )


def _existing_feedback_marker_counts(events: T.Sequence[JsonMap]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        feedback = details.get("feedback") if isinstance(details.get("feedback"), dict) else {}
        marker = feedback.get("marker")
        if isinstance(marker, str) and marker.strip():
            counts[marker] = counts.get(marker, 0) + 1
    return counts


def build_feedback_issue_drafts(
    manifest: Manifest,
    events: T.Sequence[JsonMap],
    *,
    repository: str | None = None,
    ledger_source: str = "<ledger>",
    include_blocked: bool = False,
    blocked_repeat_threshold: int = DEFAULT_BLOCKED_REPEAT_THRESHOLD,
) -> list[FeedbackIssueDraft]:
    if blocked_repeat_threshold < 1:
        raise ValueError("blocked_repeat_threshold must be at least 1")

    target_repository = repository or default_repository(manifest)
    harness_id = str(manifest.get("id", "unknown-harness"))
    existing_feedback_counts = _existing_feedback_marker_counts(events)
    grouped: dict[str, list[JsonMap]] = {}

    for event in events:
        if not is_feedback_candidate(event, include_blocked=include_blocked):
            continue
        eval_id, _, _, eval_details = _eval_event_payload(event)
        marker = eval_issue_marker(target_repository, harness_id, eval_id, eval_details)
        grouped.setdefault(marker, []).append(event)

    drafts: list[FeedbackIssueDraft] = []
    for marker, matching_events in grouped.items():
        latest_event = matching_events[-1]
        _, status, _, _ = _eval_event_payload(latest_event)
        existing_feedback_events = existing_feedback_counts.get(marker, 0)
        if (
            status == "blocked"
            and len(matching_events) < blocked_repeat_threshold
            and existing_feedback_events == 0
        ):
            continue
        drafts.append(
            build_feedback_issue_draft(
                manifest,
                latest_event,
                repository=target_repository,
                ledger_source=ledger_source,
                occurrence_count=len(matching_events),
                existing_feedback_events=existing_feedback_events,
            )
        )
    return drafts


def eval_result_to_event(
    result: EvalResult,
    *,
    run_id: str,
    sequence: int,
    timestamp: str,
) -> JsonMap:
    return {
        "run_id": run_id,
        "sequence": sequence,
        "timestamp": timestamp,
        "type": "eval.result",
        "status": result.status,
        "message": result.message,
        "action_id": None,
        "details": {"eval_id": result.id, "eval": result.to_dict()},
    }


def build_feedback_issue_drafts_from_results(
    manifest: Manifest,
    results: T.Sequence[EvalResult],
    *,
    repository: str | None = None,
    ledger_events: T.Sequence[JsonMap] = (),
    ledger_source: str = "<direct-eval-results>",
    include_blocked: bool = False,
    blocked_repeat_threshold: int = 1,
    run_id: str | None = None,
    timestamp: str | None = None,
) -> list[FeedbackIssueDraft]:
    if blocked_repeat_threshold < 1:
        raise ValueError("blocked_repeat_threshold must be at least 1")

    target_repository = repository or default_repository(manifest)
    harness_id = str(manifest.get("id", "unknown-harness"))
    existing_feedback_counts = _existing_feedback_marker_counts(ledger_events)
    historical_eval_counts = _historical_eval_marker_counts(
        target_repository,
        harness_id,
        ledger_events,
        include_blocked=include_blocked,
    )
    result_run_id = run_id or _run_id_from_events(ledger_events)
    event_time = timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    start_sequence = _next_sequence(ledger_events)

    drafts: list[FeedbackIssueDraft] = []
    for offset, result in enumerate(results):
        event = eval_result_to_event(
            result,
            run_id=result_run_id,
            sequence=start_sequence + offset,
            timestamp=event_time,
        )
        if not is_feedback_candidate(event, include_blocked=include_blocked):
            continue
        eval_id, status, _, eval_details = _eval_event_payload(event)
        marker = eval_issue_marker(target_repository, harness_id, eval_id, eval_details)
        occurrence_count = historical_eval_counts.get(marker, 0) + 1
        existing_feedback_events = existing_feedback_counts.get(marker, 0)
        if (
            status == "blocked"
            and occurrence_count < blocked_repeat_threshold
            and existing_feedback_events == 0
        ):
            continue
        drafts.append(
            build_feedback_issue_draft(
                manifest,
                event,
                repository=target_repository,
                ledger_source=ledger_source,
                occurrence_count=occurrence_count,
                existing_feedback_events=existing_feedback_events,
            )
        )
    return drafts


def _historical_eval_marker_counts(
    repository: str,
    harness_id: str,
    events: T.Sequence[JsonMap],
    *,
    include_blocked: bool,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        if not is_feedback_candidate(event, include_blocked=include_blocked):
            continue
        eval_id, _, _, eval_details = _eval_event_payload(event)
        marker = eval_issue_marker(repository, harness_id, eval_id, eval_details)
        counts[marker] = counts.get(marker, 0) + 1
    return counts


def _run_id_from_events(events: T.Sequence[JsonMap]) -> str:
    if events:
        run_id = events[0].get("run_id")
        if isinstance(run_id, str) and run_id.strip():
            return run_id
    return "eval-run"


def _next_sequence(events: T.Sequence[JsonMap]) -> int:
    sequences = [event.get("sequence") for event in events]
    concrete = [sequence for sequence in sequences if isinstance(sequence, int)]
    return max(concrete, default=0) + 1


def feedback_drafts_to_events(
    drafts: T.Sequence[FeedbackIssueDraft],
    *,
    run_id: str,
    start_sequence: int,
    timestamp: str | None = None,
) -> list[LedgerEvent]:
    event_time = timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    events: list[LedgerEvent] = []
    for draft in drafts:
        for adapter_event in draft.adapter_result.ledger_events:
            details = dict(adapter_event.details)
            details["feedback"] = {
                "eval_id": draft.eval_id,
                "status": draft.status,
                "marker": draft.marker,
                "operation": draft.operation,
                "occurrence_count": draft.occurrence_count,
                "existing_feedback_events": draft.existing_feedback_events,
                "source_sequence": draft.source_event.get("sequence"),
            }
            details["adapter_result"] = {
                "status": draft.adapter_result.status,
                "message": draft.adapter_result.message,
                "outputs": draft.adapter_result.outputs,
                "evidence": draft.adapter_result.evidence,
                "dry_run": draft.adapter_result.dry_run,
            }
            events.append(
                LedgerEvent(
                    run_id=run_id,
                    sequence=start_sequence + len(events),
                    timestamp=event_time,
                    type=adapter_event.type,
                    status=adapter_event.status,
                    message=adapter_event.message,
                    action_id=adapter_event.action_id,
                    details=details,
                )
            )
    return events


def append_feedback_events(events: T.Iterable[LedgerEvent], path: Path) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")


def render_feedback_report(drafts: T.Sequence[FeedbackIssueDraft]) -> str:
    lines = ["Feedback issue drafts", ""]
    if not drafts:
        lines.append("- none")
        return "\n".join(lines)
    for draft in drafts:
        lines.append(f"- {draft.title}")
        lines.append(f"  eval: {draft.eval_id} ({draft.status})")
        lines.append(f"  operation: {draft.operation}")
        lines.append(f"  occurrences: {draft.occurrence_count}")
        lines.append(f"  marker: {draft.marker}")
        lines.append(f"  action: {draft.adapter_result.action_id}")
    return "\n".join(lines)
