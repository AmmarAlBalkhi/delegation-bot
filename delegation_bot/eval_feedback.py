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
    existing_live_issue_events: int = 0
    live_issue_number: int | None = None
    live_issue_url: str | None = None
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
            "existing_live_issue_events": self.existing_live_issue_events,
            "live_issue_number": self.live_issue_number,
            "live_issue_url": self.live_issue_url,
            "source_event": self.source_event,
        }


@dataclass(frozen=True)
class FeedbackIssueMemory:
    existing_feedback_events: int = 0
    existing_live_issue_events: int = 0
    live_issue_number: int | None = None
    live_issue_url: str | None = None

    @property
    def has_existing_signal(self) -> bool:
        return self.existing_feedback_events > 0 or self.existing_live_issue_events > 0


@dataclass(frozen=True)
class FeedbackResolutionTarget:
    eval_id: str
    marker: str
    existing_feedback_events: int = 0
    existing_live_issue_events: int = 0
    live_issue_number: int | None = None
    live_issue_url: str | None = None
    last_problem_sequence: int | None = None
    last_resolution_sequence: int | None = None

    @property
    def has_live_issue(self) -> bool:
        return self.existing_live_issue_events > 0 or self.live_issue_number is not None or bool(self.live_issue_url)

    def needs_resolution_for(self, event: JsonMap) -> bool:
        sequence = event.get("sequence") if isinstance(event.get("sequence"), int) else None
        if self.last_problem_sequence is None or not self.has_live_issue:
            return False
        if sequence is not None and sequence <= self.last_problem_sequence:
            return False
        if self.last_resolution_sequence is not None and self.last_resolution_sequence >= self.last_problem_sequence:
            return False
        return True


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
    existing_live_issue_events: int = 0,
    live_issue_number: int | None = None,
    live_issue_url: str | None = None,
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
            f"- existing live issue events in this ledger: `{existing_live_issue_events}`",
            f"- live GitHub issue: {_live_issue_reference(live_issue_number, live_issue_url)}",
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


def _live_issue_reference(issue_number: int | None, issue_url: str | None) -> str:
    if issue_number is None and not issue_url:
        return "`none`"
    parts: list[str] = []
    if issue_number is not None:
        parts.append(f"`#{issue_number}`")
    if issue_url:
        parts.append(issue_url)
    return " ".join(parts)


def issue_body_for_eval_recovery(
    *,
    marker: str,
    event: JsonMap,
    eval_details: JsonMap,
    ledger_source: str,
    target: FeedbackResolutionTarget,
) -> str:
    sanitized = sanitize_details(eval_details)
    run_id = event.get("run_id", "unknown")
    sequence = event.get("sequence", "unknown")
    return "\n".join(
        [
            f"<!-- {marker} -->",
            "",
            "## What Recovered",
            "",
            "The eval is passing again after a prior feedback issue.",
            "",
            "## Recovery Evidence",
            "",
            f"- eval: `{target.eval_id}`",
            f"- run_id: `{run_id}`",
            f"- sequence: `{sequence}`",
            f"- status: `passed`",
            f"- source ledger: `{ledger_source}`",
            f"- live GitHub issue: {_live_issue_reference(target.live_issue_number, target.live_issue_url)}",
            "",
            "## Prior Feedback",
            "",
            f"- feedback marker: `{target.marker}`",
            f"- prior feedback events: `{target.existing_feedback_events}`",
            f"- live issue events: `{target.existing_live_issue_events}`",
            f"- last problem sequence: `{target.last_problem_sequence}`",
            "",
            "## Passing Eval Details",
            "",
            "```json",
            _json_dumps(sanitized),
            "```",
            "",
            "## Suggested Resolution",
            "",
            "- [ ] confirm the eval is passing for the right reason",
            "- [ ] keep or add a regression eval so the issue stays fixed",
            "- [ ] close the live feedback issue or leave a short resolution note",
            "- [ ] rerun `python scripts/qa.py` before merging the fix",
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
    existing_live_issue_events: int = 0,
    live_issue_number: int | None = None,
    live_issue_url: str | None = None,
) -> FeedbackIssueDraft:
    adapter = get_builtin_adapter("github.issue")
    if not adapter:
        raise LookupError("github.issue dry-run adapter is required for feedback drafts")

    eval_id, status, message, eval_details = _eval_event_payload(event)
    harness_id = str(manifest.get("id", "unknown-harness"))
    marker = eval_issue_marker(repository, harness_id, eval_id, eval_details)
    issue_status = "failed" if status == "failed" else "blocked"
    operation = (
        "update"
        if (
            occurrence_count > 1
            or existing_feedback_events
            or existing_live_issue_events
            or live_issue_number
            or live_issue_url
        )
        else "create"
    )
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
        existing_live_issue_events=existing_live_issue_events,
        live_issue_number=live_issue_number,
        live_issue_url=live_issue_url,
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
        existing_live_issue_events=existing_live_issue_events,
        live_issue_number=live_issue_number,
        live_issue_url=live_issue_url,
        source_event=event,
    )


def build_feedback_resolution_draft(
    manifest: Manifest,
    event: JsonMap,
    *,
    target: FeedbackResolutionTarget,
    repository: str,
    ledger_source: str,
) -> FeedbackIssueDraft:
    adapter = get_builtin_adapter("github.issue")
    if not adapter:
        raise LookupError("github.issue dry-run adapter is required for feedback recovery drafts")

    _, status, _, eval_details = _eval_event_payload(event)
    if status != "passed":
        raise ValueError("feedback recovery drafts require a passed eval event")

    harness_id = str(manifest.get("id", "unknown-harness"))
    title = f"Resolve eval passed: {target.eval_id}"
    body = issue_body_for_eval_recovery(
        marker=target.marker,
        event=event,
        eval_details=eval_details,
        ledger_source=ledger_source,
        target=target,
    )
    request = AdapterRequest(
        adapter_id="github.issue",
        action_id=f"feedback.resolve.{target.eval_id}.{target.marker.rsplit(':', 1)[-1]}",
        mission_id=harness_id,
        objective=f"Draft recovery update for eval feedback issue `{target.eval_id}`.",
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
        eval_id=target.eval_id,
        status="passed",
        marker=target.marker,
        title=title,
        body=body,
        adapter_result=result,
        operation="resolve",
        occurrence_count=1,
        existing_feedback_events=target.existing_feedback_events,
        existing_live_issue_events=target.existing_live_issue_events,
        live_issue_number=target.live_issue_number,
        live_issue_url=target.live_issue_url,
        source_event=event,
    )


def _existing_feedback_memory(events: T.Sequence[JsonMap]) -> dict[str, FeedbackIssueMemory]:
    working: dict[str, JsonMap] = {}

    def ensure(marker: str) -> JsonMap:
        return working.setdefault(
            marker,
            {
                "existing_feedback_events": 0,
                "existing_live_issue_events": 0,
                "live_issue_number": None,
                "live_issue_url": None,
            },
        )

    for event in events:
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        feedback = details.get("feedback") if isinstance(details.get("feedback"), dict) else {}
        marker = feedback.get("marker")
        if isinstance(marker, str) and marker.strip():
            ensure(marker)["existing_feedback_events"] += 1

        if event.get("type") not in {"github.issue.created", "github.issue.updated"}:
            continue
        issue_marker = details.get("issue_marker")
        if not isinstance(issue_marker, str) or not issue_marker.strip():
            continue
        entry = ensure(issue_marker)
        entry["existing_live_issue_events"] += 1
        issue_number = _issue_number(details.get("issue_number"))
        issue_url = details.get("issue_url") if isinstance(details.get("issue_url"), str) else None
        if issue_number is not None:
            entry["live_issue_number"] = issue_number
        if issue_url:
            entry["live_issue_url"] = issue_url

    return {
        marker: FeedbackIssueMemory(
            existing_feedback_events=int(entry["existing_feedback_events"]),
            existing_live_issue_events=int(entry["existing_live_issue_events"]),
            live_issue_number=T.cast(int | None, entry["live_issue_number"]),
            live_issue_url=T.cast(str | None, entry["live_issue_url"]),
        )
        for marker, entry in working.items()
    }


def _issue_number(value: T.Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _feedback_resolution_targets(events: T.Sequence[JsonMap]) -> dict[str, FeedbackResolutionTarget]:
    working: dict[str, JsonMap] = {}

    def ensure(marker: str, eval_id: str | None = None) -> JsonMap:
        resolved_eval_id = eval_id or _eval_id_from_marker(marker) or "unknown"
        entry = working.setdefault(
            marker,
            {
                "eval_id": resolved_eval_id,
                "marker": marker,
                "existing_feedback_events": 0,
                "existing_live_issue_events": 0,
                "live_issue_number": None,
                "live_issue_url": None,
                "last_problem_sequence": None,
                "last_resolution_sequence": None,
            },
        )
        if entry["eval_id"] == "unknown" and resolved_eval_id != "unknown":
            entry["eval_id"] = resolved_eval_id
        return entry

    for event in events:
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        sequence = event.get("sequence") if isinstance(event.get("sequence"), int) else None
        feedback = details.get("feedback") if isinstance(details.get("feedback"), dict) else {}
        marker = feedback.get("marker")
        if isinstance(marker, str) and marker.strip():
            eval_id = feedback.get("eval_id") if isinstance(feedback.get("eval_id"), str) else None
            entry = ensure(marker, eval_id)
            entry["existing_feedback_events"] += 1
            operation = feedback.get("operation") if isinstance(feedback.get("operation"), str) else ""
            if operation == "resolve":
                entry["last_resolution_sequence"] = _max_sequence(entry["last_resolution_sequence"], sequence)
            else:
                entry["last_problem_sequence"] = _max_sequence(entry["last_problem_sequence"], sequence)
            if isinstance(feedback.get("live_issue_number"), int):
                entry["live_issue_number"] = feedback["live_issue_number"]
            if isinstance(feedback.get("live_issue_url"), str):
                entry["live_issue_url"] = feedback["live_issue_url"]

        if event.get("type") not in {"github.issue.created", "github.issue.updated"}:
            continue
        issue_marker = details.get("issue_marker")
        if not isinstance(issue_marker, str) or not issue_marker.strip():
            continue
        entry = ensure(issue_marker)
        entry["existing_live_issue_events"] += 1
        issue_number = _issue_number(details.get("issue_number"))
        if issue_number is not None:
            entry["live_issue_number"] = issue_number
        if isinstance(details.get("issue_url"), str):
            entry["live_issue_url"] = details["issue_url"]

    return {
        marker: FeedbackResolutionTarget(
            eval_id=str(entry["eval_id"]),
            marker=marker,
            existing_feedback_events=int(entry["existing_feedback_events"]),
            existing_live_issue_events=int(entry["existing_live_issue_events"]),
            live_issue_number=T.cast(int | None, entry["live_issue_number"]),
            live_issue_url=T.cast(str | None, entry["live_issue_url"]),
            last_problem_sequence=T.cast(int | None, entry["last_problem_sequence"]),
            last_resolution_sequence=T.cast(int | None, entry["last_resolution_sequence"]),
        )
        for marker, entry in working.items()
        if entry["eval_id"] != "unknown"
    }


def _max_sequence(current: T.Any, candidate: int | None) -> int | None:
    if candidate is None:
        return current if isinstance(current, int) else None
    if isinstance(current, int):
        return max(current, candidate)
    return candidate


def _eval_id_from_marker(marker: str) -> str | None:
    parts = marker.split(":")
    if len(parts) >= 4 and parts[0] == "delegation-bot" and parts[1] == "eval" and parts[2]:
        return parts[2]
    return None


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
    existing_feedback_memory = _existing_feedback_memory(events)
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
        memory = existing_feedback_memory.get(marker, FeedbackIssueMemory())
        if (
            status == "blocked"
            and len(matching_events) < blocked_repeat_threshold
            and not memory.has_existing_signal
        ):
            continue
        drafts.append(
            build_feedback_issue_draft(
                manifest,
                latest_event,
                repository=target_repository,
                ledger_source=ledger_source,
                occurrence_count=len(matching_events),
                existing_feedback_events=memory.existing_feedback_events,
                existing_live_issue_events=memory.existing_live_issue_events,
                live_issue_number=memory.live_issue_number,
                live_issue_url=memory.live_issue_url,
            )
        )
    return drafts


def build_feedback_resolution_drafts(
    manifest: Manifest,
    events: T.Sequence[JsonMap],
    *,
    repository: str | None = None,
    ledger_source: str = "<ledger>",
) -> list[FeedbackIssueDraft]:
    target_repository = repository or default_repository(manifest)
    targets = _feedback_resolution_targets(events)
    latest_passed: dict[str, JsonMap] = {}
    for event in events:
        if event.get("type") != "eval.result" or event.get("status") != "passed":
            continue
        eval_id, _, _, _ = _eval_event_payload(event)
        latest_passed[eval_id] = event

    drafts: list[FeedbackIssueDraft] = []
    for target in targets.values():
        event = latest_passed.get(target.eval_id)
        if event is None or not target.needs_resolution_for(event):
            continue
        drafts.append(
            build_feedback_resolution_draft(
                manifest,
                event,
                target=target,
                repository=target_repository,
                ledger_source=ledger_source,
            )
        )
    return sorted(drafts, key=lambda draft: (draft.eval_id, draft.marker))


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
    existing_feedback_memory = _existing_feedback_memory(ledger_events)
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
        memory = existing_feedback_memory.get(marker, FeedbackIssueMemory())
        if (
            status == "blocked"
            and occurrence_count < blocked_repeat_threshold
            and not memory.has_existing_signal
        ):
            continue
        drafts.append(
            build_feedback_issue_draft(
                manifest,
                event,
                repository=target_repository,
                ledger_source=ledger_source,
                occurrence_count=occurrence_count,
                existing_feedback_events=memory.existing_feedback_events,
                existing_live_issue_events=memory.existing_live_issue_events,
                live_issue_number=memory.live_issue_number,
                live_issue_url=memory.live_issue_url,
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
                "existing_live_issue_events": draft.existing_live_issue_events,
                "live_issue_number": draft.live_issue_number,
                "live_issue_url": draft.live_issue_url,
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
        if draft.live_issue_number is not None or draft.live_issue_url:
            lines.append(f"  live issue: {_live_issue_reference(draft.live_issue_number, draft.live_issue_url)}")
        lines.append(f"  marker: {draft.marker}")
        lines.append(f"  action: {draft.adapter_result.action_id}")
    return "\n".join(lines)
