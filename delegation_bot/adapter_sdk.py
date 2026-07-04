#!/usr/bin/env python3
"""Small SDK surface for Delegation Bot adapters."""

from __future__ import annotations

import typing as T
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from delegation_bot.adapters import AdapterContract


JsonMap = dict[str, T.Any]

VALID_ADAPTER_KINDS = {"workflow", "ai_harness", "model_provider", "tool", "ml_model", "human"}
VALID_ADAPTER_RISKS = {"low", "medium", "high"}
VALID_RESULT_STATUSES = {"planned", "blocked", "running", "succeeded", "failed", "skipped"}


class AdapterError(ValueError):
    """Raised when an adapter cannot accept an SDK request."""


@dataclass(frozen=True)
class AdapterRequest:
    """Input envelope passed to an adapter.

    The request is intentionally boring: one action, one adapter, a dict of
    declared inputs, plus optional metadata copied from the Harnessfile plan.
    """

    adapter_id: str
    action_id: str
    mission_id: str
    objective: str
    inputs: JsonMap = field(default_factory=dict)
    metadata: JsonMap = field(default_factory=dict)
    dry_run: bool = True

    def to_dict(self) -> JsonMap:
        return {
            "adapter_id": self.adapter_id,
            "action_id": self.action_id,
            "mission_id": self.mission_id,
            "objective": self.objective,
            "inputs": self.inputs,
            "metadata": self.metadata,
            "dry_run": self.dry_run,
        }


@dataclass(frozen=True)
class AdapterEvent:
    """Ledger-ready event emitted by an adapter result."""

    type: str
    status: str
    message: str
    action_id: str | None = None
    details: JsonMap = field(default_factory=dict)

    def to_dict(self) -> JsonMap:
        return {
            "type": self.type,
            "status": self.status,
            "message": self.message,
            "action_id": self.action_id,
            "details": self.details,
        }


@dataclass(frozen=True)
class AdapterResult:
    """Output envelope returned by an adapter."""

    adapter_id: str
    action_id: str
    status: str
    message: str
    outputs: JsonMap = field(default_factory=dict)
    evidence: JsonMap = field(default_factory=dict)
    ledger_events: tuple[AdapterEvent, ...] = ()
    dry_run: bool = True

    def to_dict(self) -> JsonMap:
        return {
            "adapter_id": self.adapter_id,
            "action_id": self.action_id,
            "status": self.status,
            "message": self.message,
            "outputs": self.outputs,
            "evidence": self.evidence,
            "ledger_events": [event.to_dict() for event in self.ledger_events],
            "dry_run": self.dry_run,
        }


@runtime_checkable
class Adapter(Protocol):
    """Protocol every adapter implementation should satisfy."""

    contract: AdapterContract

    def plan(self, request: AdapterRequest) -> AdapterResult:
        """Return a dry-run plan for the requested adapter action."""


def _is_empty(value: T.Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (dict, list, tuple, set)):
        return not value
    return False


def missing_request_inputs(contract: AdapterContract, request: AdapterRequest) -> tuple[str, ...]:
    """Return contract inputs that are missing or empty in a request."""

    return tuple(input_name for input_name in contract.inputs if _is_empty(request.inputs.get(input_name)))


def validate_adapter_contract(contract: AdapterContract) -> list[str]:
    """Validate the static contract shape for an adapter."""

    errors: list[str] = []
    if not contract.id.strip():
        errors.append("contract id must be a non-empty string")
    if contract.kind not in VALID_ADAPTER_KINDS:
        errors.append(f"`{contract.id}.kind` must be one of {sorted(VALID_ADAPTER_KINDS)}")
    if contract.risk not in VALID_ADAPTER_RISKS:
        errors.append(f"`{contract.id}.risk` must be one of {sorted(VALID_ADAPTER_RISKS)}")
    if not contract.description.strip():
        errors.append(f"`{contract.id}.description` must be non-empty")
    for field_name, values in (
        ("inputs", contract.inputs),
        ("outputs", contract.outputs),
        ("planned_event_types", contract.planned_event_types),
        ("required_evidence", contract.required_evidence),
    ):
        if not values:
            errors.append(f"`{contract.id}.{field_name}` must be non-empty")
        for index, value in enumerate(values):
            if not isinstance(value, str) or not value.strip():
                errors.append(f"`{contract.id}.{field_name}[{index}]` must be a non-empty string")
    return errors


def validate_adapter_request(contract: AdapterContract, request: AdapterRequest) -> list[str]:
    """Validate that a request is shaped for a contract."""

    errors = validate_adapter_contract(contract)
    if request.adapter_id != contract.id:
        errors.append(f"request adapter_id `{request.adapter_id}` does not match `{contract.id}`")
    if not request.action_id.strip():
        errors.append("request action_id must be non-empty")
    if not request.mission_id.strip():
        errors.append("request mission_id must be non-empty")
    missing_inputs = missing_request_inputs(contract, request)
    if missing_inputs:
        errors.append(f"request is missing inputs: {', '.join(missing_inputs)}")
    return errors


def validate_adapter_result(contract: AdapterContract, result: AdapterResult) -> list[str]:
    """Validate that an adapter result satisfies the contract ledger promise."""

    errors = validate_adapter_contract(contract)
    if result.adapter_id != contract.id:
        errors.append(f"result adapter_id `{result.adapter_id}` does not match `{contract.id}`")
    if not result.action_id.strip():
        errors.append("result action_id must be non-empty")
    if result.status not in VALID_RESULT_STATUSES:
        errors.append(f"result status `{result.status}` must be one of {sorted(VALID_RESULT_STATUSES)}")
    if not result.message.strip():
        errors.append("result message must be non-empty")

    event_types = {event.type for event in result.ledger_events}
    for event_type in contract.planned_event_types:
        if event_type not in event_types:
            errors.append(f"result is missing planned event `{event_type}`")
    for index, event in enumerate(result.ledger_events):
        if not event.type.strip():
            errors.append(f"ledger_events[{index}].type must be non-empty")
        if event.status not in VALID_RESULT_STATUSES:
            errors.append(f"ledger_events[{index}].status `{event.status}` is not valid")
        if not event.message.strip():
            errors.append(f"ledger_events[{index}].message must be non-empty")

    for evidence_key in contract.required_evidence:
        if _is_empty(result.evidence.get(evidence_key)):
            errors.append(f"result evidence is missing `{evidence_key}`")

    for output_key in contract.outputs:
        if output_key == "run_ledger":
            continue
        if _is_empty(result.outputs.get(output_key)):
            errors.append(f"result output is missing `{output_key}`")
    return errors


class ContractBackedDryRunAdapter:
    """Base implementation for adapters that only plan and emit evidence."""

    supports_live_execution = False

    def __init__(self, contract: AdapterContract) -> None:
        self.contract = contract

    def plan(self, request: AdapterRequest) -> AdapterResult:
        if request.adapter_id != self.contract.id:
            raise AdapterError(f"request adapter_id `{request.adapter_id}` does not match `{self.contract.id}`")

        missing_inputs = missing_request_inputs(self.contract, request)
        status = "blocked" if missing_inputs else "planned"
        outputs = self.build_outputs(request, missing_inputs)
        evidence = self.build_evidence(request, missing_inputs)
        events = self.build_events(request, status, missing_inputs, outputs, evidence)

        return AdapterResult(
            adapter_id=self.contract.id,
            action_id=request.action_id,
            status=status,
            message=self.build_message(request, status, missing_inputs),
            outputs=outputs,
            evidence=evidence,
            ledger_events=events,
            dry_run=True,
        )

    def build_message(
        self,
        request: AdapterRequest,
        status: str,
        missing_inputs: tuple[str, ...],
    ) -> str:
        if status == "blocked":
            return f"Dry-run blocked for `{request.action_id}` because required inputs are missing."
        return f"Dry-run planned for `{request.action_id}`."

    def build_outputs(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        outputs: JsonMap = {}
        for output_key in self.contract.outputs:
            if output_key == "run_ledger":
                continue
            outputs[output_key] = {
                "adapter": self.contract.id,
                "action_id": request.action_id,
                "planned": True,
                "dry_run": True,
                "missing_inputs": list(missing_inputs),
            }
        return outputs

    def build_evidence(self, request: AdapterRequest, missing_inputs: tuple[str, ...]) -> JsonMap:
        evidence = {
            evidence_key: f"dry-run:{self.contract.id}:{request.action_id}:{evidence_key}"
            for evidence_key in self.contract.required_evidence
        }
        if missing_inputs:
            evidence["missing_inputs"] = list(missing_inputs)
        return evidence

    def build_events(
        self,
        request: AdapterRequest,
        status: str,
        missing_inputs: tuple[str, ...],
        outputs: JsonMap,
        evidence: JsonMap,
    ) -> tuple[AdapterEvent, ...]:
        details = {
            "adapter": self.contract.id,
            "contract_kind": self.contract.kind,
            "risk": self.contract.risk,
            "dry_run": True,
            "missing_inputs": list(missing_inputs),
            "output_keys": sorted(outputs),
            "evidence_keys": sorted(evidence),
        }
        return tuple(
            AdapterEvent(
                type=event_type,
                status=status,
                action_id=request.action_id,
                message=f"Dry-run adapter event `{event_type}`.",
                details=details,
            )
            for event_type in self.contract.planned_event_types
        )
