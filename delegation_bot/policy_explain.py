"""Explain local-classifier policy evidence without changing decisions."""

from __future__ import annotations

import json
import typing as T
from dataclasses import dataclass

from delegation_bot.model_suggest_live import (
    LiveModelConfig,
    LiveModelSuggestionError,
    _extract_ollama_text,
    _json_from_model_text,
    _ollama_generate_url,
    _post_json,
)


JsonMap = dict[str, T.Any]
Sender = T.Callable[[str, dict[str, str], JsonMap, int], JsonMap]


class PolicyExplainError(ValueError):
    """Raised when policy explanation cannot be built."""


@dataclass(frozen=True)
class ClassifierFinding:
    action_id: str
    classification: str
    recommended_gate: str
    policy_profile: str
    reasons: tuple[str, ...]
    matched_terms: JsonMap
    event_type: str

    def to_dict(self) -> JsonMap:
        return {
            "action_id": self.action_id,
            "classification": self.classification,
            "recommended_gate": self.recommended_gate,
            "policy_profile": self.policy_profile,
            "reasons": list(self.reasons),
            "matched_terms": self.matched_terms,
            "event_type": self.event_type,
        }


@dataclass(frozen=True)
class PolicyExplanation:
    finding: ClassifierFinding
    explanation: str
    source: str = "deterministic"
    provider: str | None = None
    model: str | None = None
    authority: str = "deterministic_ledger_gates"

    def to_dict(self) -> JsonMap:
        return {
            "finding": self.finding.to_dict(),
            "explanation": self.explanation,
            "source": self.source,
            "provider": self.provider,
            "model": self.model,
            "authority": self.authority,
        }


@dataclass(frozen=True)
class PolicyExplanationReport:
    status: str
    ledger_source: str
    explanations: tuple[PolicyExplanation, ...]
    model_requested: bool = False
    blocked_reason: str | None = None

    @property
    def blocked(self) -> bool:
        return self.status == "blocked"

    def to_dict(self) -> JsonMap:
        return {
            "status": self.status,
            "ledger_source": self.ledger_source,
            "model_requested": self.model_requested,
            "blocked": self.blocked,
            "blocked_reason": self.blocked_reason,
            "explanations": [item.to_dict() for item in self.explanations],
        }


def build_policy_explanation_report(
    ledger_events: T.Sequence[JsonMap],
    *,
    ledger_source: str,
    use_model: bool = False,
    allow_live_model: bool = False,
    config: LiveModelConfig | None = None,
    sender: Sender | None = None,
) -> PolicyExplanationReport:
    findings = tuple(extract_classifier_findings(ledger_events))
    if use_model and not allow_live_model:
        return PolicyExplanationReport(
            status="blocked",
            ledger_source=ledger_source,
            explanations=tuple(_deterministic_explanation(finding) for finding in findings),
            model_requested=True,
            blocked_reason="Local model explanations are opt-in. Add --allow-live-model to call Ollama.",
        )
    if use_model and config is None:
        raise PolicyExplainError("model config is required when use_model is true")

    explanations: list[PolicyExplanation] = []
    for finding in findings:
        if use_model and config:
            explanations.append(fetch_ollama_policy_explanation(finding, config=config, sender=sender))
        else:
            explanations.append(_deterministic_explanation(finding))

    return PolicyExplanationReport(
        status="ready",
        ledger_source=ledger_source,
        explanations=tuple(explanations),
        model_requested=use_model,
    )


def extract_classifier_findings(ledger_events: T.Sequence[JsonMap]) -> T.Iterator[ClassifierFinding]:
    seen: set[tuple[str, str, str, str]] = set()
    for event in ledger_events:
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        adapter_result = details.get("adapter_result") if isinstance(details.get("adapter_result"), dict) else {}
        outputs = adapter_result.get("outputs") if isinstance(adapter_result.get("outputs"), dict) else {}
        evidence = adapter_result.get("evidence") if isinstance(adapter_result.get("evidence"), dict) else {}
        classification_output = outputs.get("classification") if isinstance(outputs.get("classification"), dict) else {}
        adapter = details.get("adapter")
        if adapter != "local.classifier" and not classification_output:
            continue
        action_id = event.get("action_id") if isinstance(event.get("action_id"), str) else "unknown"
        finding = ClassifierFinding(
            action_id=action_id,
            classification=str(classification_output.get("label") or evidence.get("classification") or "unknown"),
            recommended_gate=str(
                classification_output.get("recommended_gate") or evidence.get("recommended_gate") or "unknown"
            ),
            policy_profile=str(
                classification_output.get("policy_profile") or evidence.get("policy_profile") or "unknown"
            ),
            reasons=tuple(str(reason) for reason in _as_list(classification_output.get("reasons"))),
            matched_terms=classification_output.get("matched_terms")
            if isinstance(classification_output.get("matched_terms"), dict)
            else {},
            event_type=str(event.get("type") or "unknown"),
        )
        key = (finding.action_id, finding.classification, finding.recommended_gate, finding.policy_profile)
        if key in seen:
            continue
        seen.add(key)
        yield finding


def fetch_ollama_policy_explanation(
    finding: ClassifierFinding,
    *,
    config: LiveModelConfig,
    sender: Sender | None = None,
) -> PolicyExplanation:
    if config.provider != "ollama":
        raise PolicyExplainError("policy explanation currently supports the local `ollama` provider only")
    response = (sender or _post_json)(
        _ollama_generate_url(config),
        {"Content-Type": "application/json"},
        {
            "model": config.model,
            "system": _policy_explanation_system_prompt(),
            "prompt": _policy_explanation_user_prompt(finding),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        },
        config.timeout_seconds,
    )
    try:
        data = _json_from_model_text(_extract_ollama_text(response))
    except LiveModelSuggestionError as exc:
        raise PolicyExplainError(str(exc)) from exc
    explanation = data.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        raise PolicyExplainError("Ollama explanation response must include a non-empty `explanation` string")
    return PolicyExplanation(
        finding=finding,
        explanation=explanation.strip()[:800],
        source="model",
        provider=config.provider,
        model=config.model,
    )


def render_policy_explanation_report(report: PolicyExplanationReport) -> str:
    lines = [
        "Policy Explanation",
        "",
        f"Status: {report.status}",
        f"Ledger: {report.ledger_source}",
        f"Findings: {len(report.explanations)}",
        f"Mode: {'local model explanation' if report.model_requested else 'deterministic explanation'}",
        "",
        "Trust boundary:",
        "- Model may explain.",
        "- Deterministic gates still decide.",
    ]
    if report.blocked_reason:
        lines.extend(["", f"Blocked: {report.blocked_reason}"])

    lines.extend(["", "Findings:"])
    if not report.explanations:
        lines.append("- none")
    for item in report.explanations:
        finding = item.finding
        source = f" via {item.provider}/{item.model}" if item.provider and item.model else ""
        lines.append(f"- {finding.action_id}: {finding.classification} -> {finding.recommended_gate}{source}")
        lines.append(f"  profile: {finding.policy_profile}")
        lines.append(f"  why: {item.explanation}")
        lines.append(f"  authority: {item.authority}")
    return "\n".join(lines)


def _deterministic_explanation(finding: ClassifierFinding) -> PolicyExplanation:
    matched = _format_matched_terms(finding.matched_terms)
    reasons = "; ".join(finding.reasons) if finding.reasons else "no structured reasons were recorded"
    explanation = (
        f"Profile `{finding.policy_profile}` classified this action as `{finding.classification}` "
        f"and recommended `{finding.recommended_gate}` because {reasons}."
    )
    if matched:
        explanation += f" Matched terms: {matched}."
    explanation += " This is evidence for the gate; it is not a model approval."
    return PolicyExplanation(finding=finding, explanation=explanation)


def _format_matched_terms(matched_terms: JsonMap) -> str:
    parts: list[str] = []
    for bucket in sorted(matched_terms):
        terms = [str(term) for term in _as_list(matched_terms[bucket]) if str(term).strip()]
        if terms:
            parts.append(f"{bucket}={', '.join(terms)}")
    return "; ".join(parts)


def _policy_explanation_system_prompt() -> str:
    return "\n".join(
        [
            "You explain DelegationHQ policy evidence to a developer.",
            "Return only JSON: {\"explanation\": \"short plain-language explanation\"}.",
            "Do not change the classification or recommended gate.",
            "Do not approve actions.",
            "Say that deterministic gates remain the authority.",
            "Keep it concise and practical.",
        ]
    )


def _policy_explanation_user_prompt(finding: ClassifierFinding) -> str:
    return json.dumps(
        {
            "task": "Explain this local.classifier finding without changing the decision.",
            "finding": finding.to_dict(),
            "required_boundary": "The model may explain evidence, but deterministic ledger gates decide.",
        },
        indent=2,
        sort_keys=True,
    )


def _as_list(value: T.Any) -> list[T.Any]:
    return value if isinstance(value, list) else []
