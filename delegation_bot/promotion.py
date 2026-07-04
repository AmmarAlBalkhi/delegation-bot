#!/usr/bin/env python3
"""Evaluate whether declared agents are ready for autonomy promotion."""

from __future__ import annotations

import json
import typing as T
from dataclasses import dataclass
from pathlib import Path

from delegation_bot.harness_manifest import Manifest


JsonMap = dict[str, T.Any]


class PromotionError(ValueError):
    """Raised when promotion evidence cannot be read."""


@dataclass(frozen=True)
class PromotionDecision:
    agent_id: str
    current_level: str
    next_level: str | None
    ready: bool
    required_evals: tuple[str, ...]
    passed_evals: tuple[str, ...]
    missing_evals: tuple[str, ...]
    reason: str

    def to_dict(self) -> JsonMap:
        return {
            "agent_id": self.agent_id,
            "current_level": self.current_level,
            "next_level": self.next_level,
            "ready": self.ready,
            "required_evals": list(self.required_evals),
            "passed_evals": list(self.passed_evals),
            "missing_evals": list(self.missing_evals),
            "reason": self.reason,
        }


def load_ledger(path: Path) -> list[JsonMap]:
    events: list[JsonMap] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                data = json.loads(line)
                if not isinstance(data, dict):
                    raise PromotionError(f"Ledger line {line_number} must be a JSON object")
                events.append(data)
    except OSError as exc:
        raise PromotionError(str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise PromotionError(f"Ledger JSON error: {exc}") from exc
    return events


def _nested_eval_id(details: JsonMap) -> str | None:
    direct = details.get("eval_id")
    if isinstance(direct, str) and direct.strip():
        return direct

    eval_obj = details.get("eval")
    if isinstance(eval_obj, dict) and isinstance(eval_obj.get("id"), str):
        return eval_obj["id"]

    action = details.get("action")
    if isinstance(action, dict):
        metadata = action.get("metadata")
        if isinstance(metadata, dict):
            nested_eval = metadata.get("eval")
            if isinstance(nested_eval, dict) and isinstance(nested_eval.get("id"), str):
                return nested_eval["id"]
    return None


def event_eval_id(event: JsonMap) -> str | None:
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    nested = _nested_eval_id(details)
    if nested:
        return nested

    event_type = event.get("type")
    if not isinstance(event_type, str):
        return None
    parts = event_type.split(".")
    if len(parts) >= 2 and parts[0] == "eval" and parts[1] not in {"result", "schedule"}:
        return parts[1]
    return None


def passed_eval_ids(events: T.Iterable[JsonMap]) -> set[str]:
    passed: set[str] = set()
    for event in events:
        if event.get("status") != "passed":
            continue
        eval_id = event_eval_id(event)
        if eval_id:
            passed.add(eval_id)
    return passed


def evaluate_promotions(manifest: Manifest, ledger_events: T.Iterable[JsonMap]) -> list[PromotionDecision]:
    passed = passed_eval_ids(ledger_events)
    decisions: list[PromotionDecision] = []

    agents = manifest.get("agents") if isinstance(manifest.get("agents"), list) else []
    for index, agent in enumerate(agents):
        if not isinstance(agent, dict):
            continue
        agent_id = agent.get("id") if isinstance(agent.get("id"), str) else f"agent_{index + 1}"
        current_level = agent.get("autonomy_level") if isinstance(agent.get("autonomy_level"), str) else "suggest"
        promotion = agent.get("promotion") if isinstance(agent.get("promotion"), dict) else {}
        next_level = promotion.get("next_level") if isinstance(promotion.get("next_level"), str) else None
        required_items = promotion.get("requires_evals", [])
        required = tuple(
            item
            for item in required_items
            if isinstance(required_items, list) and isinstance(item, str)
        )

        if not next_level:
            decisions.append(
                PromotionDecision(
                    agent_id=agent_id,
                    current_level=current_level,
                    next_level=None,
                    ready=False,
                    required_evals=(),
                    passed_evals=(),
                    missing_evals=(),
                    reason="No promotion rule declared.",
                )
            )
            continue

        if not required:
            decisions.append(
                PromotionDecision(
                    agent_id=agent_id,
                    current_level=current_level,
                    next_level=next_level,
                    ready=False,
                    required_evals=(),
                    passed_evals=(),
                    missing_evals=(),
                    reason="No required evals declared for automatic promotion.",
                )
            )
            continue

        required_set = set(required)
        passed_required = tuple(sorted(required_set & passed))
        missing = tuple(sorted(required_set - passed))
        ready = not missing
        decisions.append(
            PromotionDecision(
                agent_id=agent_id,
                current_level=current_level,
                next_level=next_level,
                ready=ready,
                required_evals=tuple(sorted(required_set)),
                passed_evals=passed_required,
                missing_evals=missing,
                reason="All required evals passed." if ready else "Missing required eval evidence.",
            )
        )
    return decisions


def render_promotion_report(decisions: T.Sequence[PromotionDecision]) -> str:
    lines = ["Promotion report", ""]
    if not decisions:
        lines.append("No agents declared.")
        return "\n".join(lines)

    for decision in decisions:
        target = f"{decision.current_level} -> {decision.next_level}" if decision.next_level else decision.current_level
        status = "ready" if decision.ready else "blocked"
        lines.append(f"- {decision.agent_id}: {target} [{status}]")
        lines.append(f"  reason: {decision.reason}")
        if decision.required_evals:
            lines.append(f"  required: {', '.join(decision.required_evals)}")
            lines.append(f"  passed: {', '.join(decision.passed_evals) or 'none'}")
            lines.append(f"  missing: {', '.join(decision.missing_evals) or 'none'}")
    return "\n".join(lines)
