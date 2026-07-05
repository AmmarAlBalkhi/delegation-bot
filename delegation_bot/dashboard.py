#!/usr/bin/env python3
"""Read-only dashboard snapshot data model for Harnessfile ledgers."""

from __future__ import annotations

import typing as T
from collections import Counter
from dataclasses import dataclass, field

from delegation_bot.harness_manifest import Manifest


JsonMap = dict[str, T.Any]


@dataclass(frozen=True)
class DashboardSnapshot:
    source: str
    status: str
    next_safe_action: str
    mission: JsonMap
    counts: JsonMap
    adapters: tuple[JsonMap, ...] = ()
    evals: tuple[JsonMap, ...] = ()
    feedback: tuple[JsonMap, ...] = ()
    agents: tuple[JsonMap, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> JsonMap:
        return {
            "source": self.source,
            "status": self.status,
            "next_safe_action": self.next_safe_action,
            "mission": self.mission,
            "counts": self.counts,
            "adapters": list(self.adapters),
            "evals": list(self.evals),
            "feedback": list(self.feedback),
            "agents": list(self.agents),
            "warnings": list(self.warnings),
        }


def build_dashboard_snapshot(
    events: T.Sequence[JsonMap],
    *,
    manifest: Manifest | None = None,
    source: str = "<ledger>",
) -> DashboardSnapshot:
    evals = tuple(_eval_summaries(events))
    adapters = tuple(_adapter_summaries(events))
    feedback = tuple(_feedback_summaries(events))
    agents = tuple(_agent_summaries(manifest))
    status = _dashboard_status(events, evals)
    return DashboardSnapshot(
        source=source,
        status=status,
        next_safe_action=_next_safe_action(status, evals, feedback),
        mission=_mission_summary(events, manifest),
        counts=_counts(events, evals, adapters, feedback, agents),
        adapters=adapters,
        evals=evals,
        feedback=feedback,
        agents=agents,
        warnings=_warnings(events, manifest),
    )


def render_dashboard_snapshot(snapshot: DashboardSnapshot) -> str:
    mission = snapshot.mission
    lines = [
        "Dashboard snapshot",
        "",
        f"Source: {snapshot.source}",
        f"Mission: {mission.get('id', 'unknown')}",
        f"Objective: {mission.get('objective', 'unknown')}",
        f"Status: {snapshot.status}",
        f"Mode: {mission.get('mode', 'unknown')}",
        f"Next safe action: {snapshot.next_safe_action}",
        "",
        "Counts:",
    ]
    for key, value in snapshot.counts.items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "Adapters:"])
    if snapshot.adapters:
        for adapter in snapshot.adapters:
            lines.append(
                f"- {adapter['adapter']} {adapter['action_id']} "
                f"[{adapter['latest_status']}] events={adapter['event_count']}"
            )
            if adapter.get("evidence_keys"):
                lines.append(f"  evidence: {', '.join(adapter['evidence_keys'])}")
    else:
        lines.append("- none")

    lines.extend(["", "Evals:"])
    if snapshot.evals:
        for item in snapshot.evals:
            lines.append(f"- {item['eval_id']}: {item['status']} seq={item.get('sequence')}")
            if item.get("message"):
                lines.append(f"  {item['message']}")
    else:
        lines.append("- none")

    lines.extend(["", "Feedback:"])
    if snapshot.feedback:
        for item in snapshot.feedback:
            issue = _format_issue_reference(item.get("live_issue_number"), item.get("live_issue_url"))
            lines.append(f"- {item['eval_id']}: {item['operation']} {item['marker']}")
            lines.append(f"  issue: {issue}")
    else:
        lines.append("- none")

    lines.extend(["", "Agents:"])
    if snapshot.agents:
        for agent in snapshot.agents:
            lines.append(
                f"- {agent['id']} runtime={agent['runtime']} "
                f"autonomy={agent['autonomy_level']} model={agent.get('model') or 'none'}"
            )
    else:
        lines.append("- none")

    if snapshot.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in snapshot.warnings)
    return "\n".join(lines)


def _mission_summary(events: T.Sequence[JsonMap], manifest: Manifest | None) -> JsonMap:
    plan = {}
    for event in events:
        if _event_type(event) == "plan.compiled":
            details = _details(event)
            candidate = details.get("plan") if isinstance(details.get("plan"), dict) else {}
            plan = candidate
    owners = manifest.get("owners") if isinstance(manifest, dict) and isinstance(manifest.get("owners"), dict) else {}
    return {
        "id": _first_string(plan.get("id"), manifest.get("id") if manifest else None, "unknown"),
        "objective": _first_string(
            plan.get("objective"),
            manifest.get("objective") if manifest else None,
            "unknown",
        ),
        "mode": _first_string(plan.get("mode"), "dry-run"),
        "repository": _manifest_repository(manifest),
        "accountable": owners.get("accountable") if isinstance(owners.get("accountable"), str) else None,
        "reviewers": owners.get("reviewers") if isinstance(owners.get("reviewers"), list) else [],
    }


def _counts(
    events: T.Sequence[JsonMap],
    evals: T.Sequence[JsonMap],
    adapters: T.Sequence[JsonMap],
    feedback: T.Sequence[JsonMap],
    agents: T.Sequence[JsonMap],
) -> JsonMap:
    return {
        "events": len(events),
        "runs": len({_event_run_id(event) for event in events if _event_run_id(event)}),
        "adapters": len(adapters),
        "evals": len(evals),
        "feedback_items": len(feedback),
        "agents": len(agents),
        "statuses": dict(sorted(Counter(_event_status(event) for event in events).items())),
    }


def _adapter_summaries(events: T.Sequence[JsonMap]) -> T.Iterator[JsonMap]:
    records: dict[tuple[str, str], JsonMap] = {}
    for event in events:
        details = _details(event)
        adapter = _adapter_id(event)
        if not adapter:
            continue
        action_id = _event_action_id(event) or "unknown"
        key = (adapter, action_id)
        adapter_result = details.get("adapter_result") if isinstance(details.get("adapter_result"), dict) else {}
        evidence = adapter_result.get("evidence") if isinstance(adapter_result.get("evidence"), dict) else {}
        record = records.setdefault(
            key,
            {
                "adapter": adapter,
                "action_id": action_id,
                "event_count": 0,
                "latest_status": "unknown",
                "latest_event_type": "unknown",
                "evidence_keys": set(),
                "issue_number": None,
                "issue_url": None,
            },
        )
        record["event_count"] += 1
        record["latest_status"] = _event_status(event)
        record["latest_event_type"] = _event_type(event)
        record["evidence_keys"].update(str(key) for key in evidence)
        if isinstance(details.get("issue_number"), int):
            record["issue_number"] = details["issue_number"]
        if isinstance(details.get("issue_url"), str):
            record["issue_url"] = details["issue_url"]
    for record in sorted(records.values(), key=lambda item: (item["adapter"], item["action_id"])):
        yield {
            **record,
            "evidence_keys": sorted(record["evidence_keys"]),
        }


def _eval_summaries(events: T.Sequence[JsonMap]) -> T.Iterator[JsonMap]:
    latest: dict[str, JsonMap] = {}
    for event in events:
        if _event_type(event) != "eval.result":
            continue
        details = _details(event)
        eval_payload = details.get("eval") if isinstance(details.get("eval"), dict) else {}
        eval_id = details.get("eval_id") if isinstance(details.get("eval_id"), str) else eval_payload.get("id")
        if not isinstance(eval_id, str) or not eval_id.strip():
            eval_id = "unknown"
        latest[eval_id] = {
            "eval_id": eval_id,
            "status": _event_status(event),
            "message": _event_message(event),
            "sequence": _event_sequence(event),
            "details": eval_payload.get("details") if isinstance(eval_payload.get("details"), dict) else {},
        }
    yield from sorted(latest.values(), key=lambda item: item["eval_id"])


def _feedback_summaries(events: T.Sequence[JsonMap]) -> T.Iterator[JsonMap]:
    records: dict[str, JsonMap] = {}
    for event in events:
        details = _details(event)
        feedback = details.get("feedback") if isinstance(details.get("feedback"), dict) else {}
        marker = feedback.get("marker")
        if isinstance(marker, str) and marker.strip():
            record = records.setdefault(marker, _empty_feedback(marker))
            record.update(
                {
                    "eval_id": feedback.get("eval_id") or record["eval_id"],
                    "eval_status": feedback.get("status") or record["eval_status"],
                    "operation": feedback.get("operation") or record["operation"],
                    "sequence": _event_sequence(event),
                }
            )
            if isinstance(feedback.get("live_issue_number"), int):
                record["live_issue_number"] = feedback["live_issue_number"]
            if isinstance(feedback.get("live_issue_url"), str):
                record["live_issue_url"] = feedback["live_issue_url"]

        issue_marker = details.get("issue_marker")
        if not isinstance(issue_marker, str) or not issue_marker.strip():
            continue
        record = records.setdefault(issue_marker, _empty_feedback(issue_marker))
        if isinstance(details.get("issue_number"), int):
            record["live_issue_number"] = details["issue_number"]
        if isinstance(details.get("issue_url"), str):
            record["live_issue_url"] = details["issue_url"]
    yield from sorted(records.values(), key=lambda item: (str(item["eval_id"]), str(item["marker"])))


def _empty_feedback(marker: str) -> JsonMap:
    return {
        "marker": marker,
        "eval_id": "unknown",
        "eval_status": "unknown",
        "operation": "unknown",
        "sequence": None,
        "live_issue_number": None,
        "live_issue_url": None,
    }


def _agent_summaries(manifest: Manifest | None) -> T.Iterator[JsonMap]:
    agents = manifest.get("agents") if isinstance(manifest, dict) and isinstance(manifest.get("agents"), list) else []
    for agent in agents:
        if not isinstance(agent, dict):
            continue
        yield {
            "id": str(agent.get("id") or "unknown"),
            "runtime": str(agent.get("runtime") or "unknown"),
            "autonomy_level": str(agent.get("autonomy_level") or "unknown"),
            "model": agent.get("model") if isinstance(agent.get("model"), str) else None,
            "capability_packs": agent.get("capability_packs") if isinstance(agent.get("capability_packs"), list) else [],
        }


def _dashboard_status(events: T.Sequence[JsonMap], evals: T.Sequence[JsonMap]) -> str:
    eval_statuses = {str(item.get("status")) for item in evals}
    if "failed" in eval_statuses:
        return "failed"
    if "blocked" in eval_statuses:
        return "blocked"
    if evals and eval_statuses == {"passed"}:
        return "ready"
    if any(_event_status(event) == "failed" for event in events):
        return "needs_attention"
    if events:
        return "planned"
    return "empty"


def _next_safe_action(status: str, evals: T.Sequence[JsonMap], feedback: T.Sequence[JsonMap]) -> str:
    if status == "failed":
        failed = [item["eval_id"] for item in evals if item.get("status") == "failed"]
        return "Fix failed evals, then rerun `delegation eval`." if not failed else f"Fix eval `{failed[0]}`, then rerun `delegation eval`."
    if status == "blocked":
        blocked = [item["eval_id"] for item in evals if item.get("status") == "blocked"]
        return "Add missing evidence, then rerun evals." if not blocked else f"Add evidence for `{blocked[0]}`, then rerun evals."
    if status == "ready" and feedback:
        return "Review feedback items and promotion readiness before live apply."
    if status == "ready":
        return "Review promotion readiness or preview live apply."
    if status == "planned":
        return "Run evals before any live apply."
    return "Create or load a dry-run ledger."


def _warnings(events: T.Sequence[JsonMap], manifest: Manifest | None) -> tuple[str, ...]:
    warnings: list[str] = []
    if not events:
        warnings.append("No ledger events were provided.")
    if manifest is None:
        warnings.append("No Harnessfile was provided, so agents and owners may be incomplete.")
    return tuple(warnings)


def _manifest_repository(manifest: Manifest | None) -> str | None:
    policies = manifest.get("policies") if isinstance(manifest, dict) and isinstance(manifest.get("policies"), dict) else {}
    permissions = policies.get("permissions") if isinstance(policies.get("permissions"), dict) else {}
    repositories = permissions.get("allowed_repositories") if isinstance(permissions.get("allowed_repositories"), list) else []
    if repositories and isinstance(repositories[0], str):
        return repositories[0]
    return None


def _details(event: JsonMap) -> JsonMap:
    return event.get("details") if isinstance(event.get("details"), dict) else {}


def _adapter_id(event: JsonMap) -> str | None:
    details = _details(event)
    adapter = details.get("adapter")
    if isinstance(adapter, str) and adapter.strip():
        return adapter
    action = details.get("action") if isinstance(details.get("action"), dict) else {}
    action_adapter = action.get("adapter")
    return action_adapter if isinstance(action_adapter, str) and action_adapter.strip() else None


def _event_type(event: JsonMap) -> str:
    return event.get("type") if isinstance(event.get("type"), str) else "unknown"


def _event_status(event: JsonMap) -> str:
    return event.get("status") if isinstance(event.get("status"), str) else "unknown"


def _event_message(event: JsonMap) -> str:
    return event.get("message") if isinstance(event.get("message"), str) else ""


def _event_action_id(event: JsonMap) -> str | None:
    return event.get("action_id") if isinstance(event.get("action_id"), str) else None


def _event_run_id(event: JsonMap) -> str | None:
    return event.get("run_id") if isinstance(event.get("run_id"), str) else None


def _event_sequence(event: JsonMap) -> int | None:
    return event.get("sequence") if isinstance(event.get("sequence"), int) else None


def _first_string(*values: T.Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return "unknown"


def _format_issue_reference(issue_number: T.Any, issue_url: T.Any) -> str:
    parts: list[str] = []
    if isinstance(issue_number, int):
        parts.append(f"#{issue_number}")
    if isinstance(issue_url, str) and issue_url:
        parts.append(issue_url)
    return " ".join(parts) if parts else "none"
