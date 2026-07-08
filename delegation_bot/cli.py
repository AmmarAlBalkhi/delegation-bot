#!/usr/bin/env python3
"""DelegationHQ command line interface."""

from __future__ import annotations

import argparse
import json
import sys
import typing as T
from pathlib import Path

from delegation_bot import __version__
from delegation_bot.agent_gate import (
    build_agent_gate_audit_report,
    build_agent_gate_events,
    build_agent_gate_report,
    render_agent_gate_audit_report,
    render_agent_gate_report,
)
from delegation_bot.agent_packet import build_agent_packet_report, render_agent_packet_report
from delegation_bot.agent_passports import build_agent_passport_report, render_agent_passport_report
from delegation_bot.agent_result import (
    build_agent_result_ingest_report,
    load_agent_result,
    render_agent_result_ingest_report,
)
from delegation_bot.agent_registry_writer import (
    DEFAULT_REGISTRY_PATH,
    add_agent_to_registry,
    render_agent_add_report,
)
from delegation_bot.agent_run import (
    DEFAULT_TIMEOUT_SECONDS as AGENT_RUN_DEFAULT_TIMEOUT_SECONDS,
    LOCAL_AGENT_EXECUTION_CONFIRMATION,
    render_agent_run_report,
    run_agent_under_control,
)
from delegation_bot.action_request import (
    build_action_request_events,
    build_action_request_report,
    render_action_request_report,
)
from delegation_bot.app_dashboard import build_app_dashboard_report, render_app_dashboard_report
from delegation_bot.app_plan import build_app_plan, render_app_plan
from delegation_bot.app_state import build_app_state, render_app_state
from delegation_bot.approval_preview import build_approval_preview_report, render_approval_preview_report
from delegation_bot.approval_inbox import (
    APPROVAL_DECISIONS,
    build_approval_decision_events,
    build_approval_decision_receipt,
    build_approval_inbox_report,
    render_approval_decision_receipt,
    render_approval_inbox_report,
)
from delegation_bot.adapters import get_adapter_contract, list_adapter_contracts, render_adapter_contracts
from delegation_bot.dashboard import build_dashboard_snapshot, render_dashboard_snapshot
from delegation_bot.doctor import render_doctor_report, run_doctor
from delegation_bot.evals import EvalError, append_jsonl, eval_results_to_events, load_jsonl, render_eval_report, run_declared_evals
from delegation_bot.evidence_report import build_evidence_report, render_evidence_report
from delegation_bot.evidence_ingest import (
    build_evidence_ingest_receipt,
    build_evidence_recording_events,
    evidence_artifacts_from_values,
    load_evidence_bundle,
    render_evidence_ingest_receipt,
)
from delegation_bot.eval_feedback import (
    append_feedback_events,
    build_feedback_issue_drafts,
    build_feedback_issue_drafts_from_results,
    build_feedback_resolution_drafts,
    feedback_drafts_to_events,
    render_feedback_report,
)
from delegation_bot.first_run import (
    DEFAULT_DEMO_LEDGER,
    DEFAULT_INIT_GOAL,
    DEFAULT_INIT_OUTPUT,
    build_control_loop_demo_report,
    build_demo_report,
    render_demo_report,
    render_init_report,
    write_init_harnessfile,
)
from delegation_bot.github_actions_apply import (
    CANCEL_CONFIRMATION,
    FORCE_CANCEL_CONFIRMATION,
    GitHubActionsClient,
    GitHubTokenDiagnostics,
    apply_github_actions_drafts,
    build_actions_apply_report,
    build_actions_cancel_report,
    cancel_github_actions_run,
    render_actions_apply_report,
    render_actions_cancel_report,
)
from delegation_bot.github_app_plan import (
    MODE_CHOICES,
    build_github_app_plan,
    render_github_app_plan,
    write_github_app_plan,
)
from delegation_bot.github_auth import (
    AUTH_CHOICES,
    AUTH_AUTO,
    AUTH_GITHUB_APP,
    ISSUE_WRITE_PERMISSIONS,
    GitHubAuthResolution,
    render_github_auth_resolution,
    resolve_github_auth_token,
)
from delegation_bot.github_issue_apply import (
    GitHubIssueClient,
    apply_feedback_resolution_drafts,
    apply_github_issue_drafts,
    build_apply_report,
    build_feedback_apply_report,
    github_token_from_env,
    render_apply_report,
    render_feedback_apply_report,
)
from delegation_bot.harness_manifest import ManifestError, load_manifest, summarize_manifest, validate_manifest
from delegation_bot.harness_plan import PlanError, build_dry_run_ledger, compile_plan, render_plan, write_jsonl
from delegation_bot.ledger import LedgerError, LedgerFilter, build_ledger_view, load_ledger_events, render_ledger_view
from delegation_bot.local_workspace import (
    DEFAULT_WORKSPACE_AGENT_RUN_LEDGER,
    DEFAULT_WORKSPACE_AGENT_RUNS_DIR,
    DEFAULT_WORKSPACE_HARNESS,
    DEFAULT_WORKSPACE_REGISTRY,
    build_workspace_status,
    initialize_local_workspace,
    render_workspace_init_report,
    render_workspace_status,
)
from delegation_bot.local_app import (
    DEFAULT_APP_HOST,
    DEFAULT_APP_PORT,
    app_server_report,
    export_local_app,
    render_local_app_report,
    serve_local_app,
)
from delegation_bot.mcp_policy_gate import build_mcp_policy_report, render_mcp_policy_report
from delegation_bot.mission_timeline import build_timeline_report_from_paths, render_timeline_report
from delegation_bot.mission_status import build_mission_status_report, render_mission_status_report
from delegation_bot.model_suggest_fixtures import (
    FIXTURE_PROVIDERS,
    ModelSuggestionFixtureError,
    load_model_suggestion_fixture,
)
from delegation_bot.model_suggest_live import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_TIMEOUT_SECONDS,
    LIVE_PROVIDERS,
    LiveModelSuggestionError,
    build_live_model_config,
    fetch_live_model_suggestion,
)
from delegation_bot.otel_export import OtelExportError, build_otel_export, render_otel_export, write_otel_export
from delegation_bot.policy_explain import (
    PolicyExplainError,
    build_policy_explanation_report,
    render_policy_explanation_report,
)
from delegation_bot.playbook_catalog import (
    PlaybookCatalogError,
    catalog_facets,
    filter_catalog,
    load_catalog,
    summarize_catalog,
    validate_catalog,
)
from delegation_bot.promotion import PromotionError, evaluate_promotions, load_ledger, render_promotion_report
from delegation_bot.release_artifacts import (
    ArtifactError,
    render_artifact_manifest,
    render_artifact_verification_report,
    verify_artifact_outputs,
    write_artifact_outputs,
)
from delegation_bot.release_rehearsal import build_release_rehearsal, render_release_rehearsal_report
from delegation_bot.release_readiness import build_release_readiness_report, render_release_readiness_report
from delegation_bot.runprint_ingest import (
    artifacts_from_values,
    build_runprint_ingest_receipt,
    build_runprint_recording_events,
    load_runprint_bundle,
    render_runprint_ingest_receipt,
)
from delegation_bot.suggest import (
    SUGGESTION_TEMPLATE_IDS,
    HarnessSuggestion,
    build_suggestion,
    infer_template,
    manifest_to_yaml,
    render_suggestion,
)


PROVIDER_CHOICES = tuple(sorted(set(FIXTURE_PROVIDERS) | set(LIVE_PROVIDERS)))


def _load_valid_manifest(path: Path) -> tuple[dict[str, T.Any] | None, int]:
    try:
        manifest = load_manifest(path)
    except (OSError, json.JSONDecodeError, ManifestError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return None, 1

    errors = validate_manifest(manifest)
    if errors:
        print("INVALID Harnessfile", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return None, 1
    return manifest, 0


def cmd_validate(args: argparse.Namespace) -> int:
    manifest, status = _load_valid_manifest(Path(args.harnessfile))
    if status != 0 or manifest is None:
        return status
    print(summarize_manifest(manifest))
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    path = Path(args.harnessfile)
    manifest, status = _load_valid_manifest(path)
    if status != 0 or manifest is None:
        return status

    try:
        plan = compile_plan(manifest, source=str(path))
    except PlanError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(plan.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_plan(plan))

    if args.ledger:
        events = build_dry_run_ledger(plan)
        write_jsonl(events, Path(args.ledger))
        print(f"\nLedger written: {args.ledger}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    try:
        if args.control_loop:
            report = build_control_loop_demo_report(
                ledger_path=Path(args.ledger),
                harnessfile=Path(args.harnessfile) if args.harnessfile else None,
                repository=args.repository,
                owner=args.owner,
                agent_id=args.control_agent,
                action=args.control_action,
                target=args.control_target,
                approver=args.approver,
            )
        else:
            report = build_demo_report(
                ledger_path=Path(args.ledger),
                harnessfile=Path(args.harnessfile) if args.harnessfile else None,
                repository=args.repository,
                owner=args.owner,
            )
    except (OSError, json.JSONDecodeError, ManifestError, PlanError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_demo_report(report))
    return 1 if report.blocked else 0


def cmd_init(args: argparse.Namespace) -> int:
    try:
        report = write_init_harnessfile(
            output_path=Path(args.output),
            goal=args.goal,
            repository=args.repository,
            owner=args.owner,
            template=args.template,
            force=args.force,
            plan=args.plan,
            ledger_path=Path(args.ledger) if args.ledger else None,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_init_report(report))
    return 0


def cmd_workspace_init(args: argparse.Namespace) -> int:
    try:
        report = initialize_local_workspace(
            root=Path(args.path),
            name=args.name,
            owner=args.owner,
            objective=args.goal,
            force=args.force,
            plan=args.plan,
            ledger_path=Path(args.ledger) if args.ledger else None,
        )
    except (OSError, RuntimeError, ValueError, FileExistsError, PlanError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_workspace_init_report(report))
    return 0


def cmd_workspace_status(args: argparse.Namespace) -> int:
    try:
        report = build_workspace_status(
            root=Path(args.path),
            ledger_path=Path(args.ledger) if args.ledger else None,
        )
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_workspace_status(report))
    return 0


def cmd_app_plan(args: argparse.Namespace) -> int:
    plan = build_app_plan()
    if args.json:
        print(json.dumps(plan.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_app_plan(plan))
    return 0


def cmd_app_state(args: argparse.Namespace) -> int:
    state = build_app_state(
        ledger_path=Path(args.ledger) if args.ledger else None,
        harnessfile=Path(args.harnessfile) if args.harnessfile else None,
        workspace_root=Path(args.workspace) if args.workspace else None,
        agent_registries=tuple(Path(path) for path in args.agent_registry or ()),
        include_github=args.github_checks,
        include_github_app=args.github_app,
        strict_artifacts=args.strict_artifacts,
        gate_agent=args.gate_agent,
        gate_action=args.gate_action,
        gate_target=args.gate_target,
        gate_risk=args.gate_risk,
        gate_approvals=tuple(args.gate_approval or ()),
        gate_evidence=tuple(args.gate_evidence or ()),
    )
    if args.json:
        print(json.dumps(state.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_app_state(state))
    return 0


def cmd_cockpit(args: argparse.Namespace) -> int:
    state = build_app_state(workspace_root=Path(args.workspace))
    if args.json:
        print(json.dumps(state.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_app_state(state))
    return 0


def cmd_app_dashboard(args: argparse.Namespace) -> int:
    try:
        report = build_app_dashboard_report(
            workspace_root=Path(args.workspace),
            preview_agent=args.preview_agent,
            preview_action=args.preview_action,
            preview_target=args.preview_target,
            preview_risk=args.preview_risk,
            preview_note=args.preview_note,
            preview_expires_at=args.preview_expires_at,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_app_dashboard_report(report))
    return 0


def cmd_approval_preview(args: argparse.Namespace) -> int:
    try:
        report = build_approval_preview_report(
            agent_id=args.agent_id,
            action=args.action,
            target=args.target,
            workspace_root=Path(args.workspace) if args.workspace else None,
            harnessfile=Path(args.harnessfile) if args.harnessfile else None,
            registry_paths=tuple(Path(path) for path in args.registry or ()),
            ledger_path=Path(args.ledger) if args.ledger else None,
            requested_risk=args.risk,
            approvals=tuple(args.approval or ()),
            evidence=tuple(args.evidence or ()),
            reviewer_note=args.review_note,
            expires_at=args.expires_at,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_approval_preview_report(report))
    return 1 if report.gate.blocked else 0


def cmd_timeline(args: argparse.Namespace) -> int:
    try:
        report = build_timeline_report_from_paths(
            ledger_path=Path(args.ledger) if args.ledger else None,
            workspace_root=Path(args.workspace) if args.workspace else None,
            limit=args.limit,
        )
    except (OSError, ValueError, LedgerError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_timeline_report(report))
    return 0


def cmd_app_export(args: argparse.Namespace) -> int:
    try:
        report = export_local_app(
            workspace_root=Path(args.workspace),
            output_dir=Path(args.output) if args.output else None,
            preview_agent=args.preview_agent,
            preview_action=args.preview_action,
            preview_target=args.preview_target,
            preview_note=args.preview_note,
            preview_expires_at=args.preview_expires_at,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_local_app_report(report))
    return 0


def cmd_app_serve(args: argparse.Namespace) -> int:
    report = app_server_report(workspace_root=Path(args.workspace), host=args.host, port=args.port)
    if args.dry_run:
        if args.json:
            print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        else:
            print(render_local_app_report(report))
        return 0

    print(render_local_app_report(report))
    print("")
    print("Press Ctrl+C to stop the local app server.")
    try:
        serve_local_app(
            workspace_root=Path(args.workspace),
            host=args.host,
            port=args.port,
            preview_agent=args.preview_agent,
            preview_action=args.preview_action,
            preview_target=args.preview_target,
            preview_note=args.preview_note,
            preview_expires_at=args.preview_expires_at,
        )
    except KeyboardInterrupt:
        print("\nStopped DelegationHQ local app server.")
        return 0
    return 0


def cmd_agents(args: argparse.Namespace) -> int:
    manifest = None
    if args.harnessfile:
        manifest, status = _load_valid_manifest(Path(args.harnessfile))
        if status != 0 or manifest is None:
            return status

    report = build_agent_passport_report(
        manifest=manifest,
        manifest_source=args.harnessfile,
        registry_paths=tuple(Path(path) for path in args.registry or ()),
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_agent_passport_report(report))
    return 0


def cmd_agent_add(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry)
    if args.workspace and args.registry == DEFAULT_REGISTRY_PATH:
        registry_path = Path(args.workspace).resolve() / DEFAULT_WORKSPACE_REGISTRY

    try:
        report = add_agent_to_registry(
            registry_path=registry_path,
            agent_id=args.agent_id,
            name=args.name,
            runtime_type=args.runtime_type,
            command=args.command,
            api_url=args.api_url,
            webhook_url=args.webhook_url,
            mcp_endpoint=args.mcp_endpoint,
            autonomy_level=args.autonomy_level,
            risk_level=args.risk_level,
            capabilities=tuple(args.capability or ()),
            allowed_tools=tuple(args.allowed_tool or ()),
            allowed_data=tuple(args.allowed_data or ()),
            approvals=tuple(args.approval or ()),
            expected_outputs=tuple(args.expected_output or ()),
            evidence=tuple(args.evidence or ()),
            promotion_evals=tuple(args.promotion_eval or ()),
            force=args.force,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_agent_add_report(report))
    return 0


def cmd_agent_run(args: argparse.Namespace) -> int:
    workspace_root = Path(args.workspace).resolve() if args.workspace else None
    harnessfile = Path(args.harnessfile) if args.harnessfile else None
    registry_paths = [Path(path) for path in args.registry or ()]
    ledger_path = Path(args.ledger) if args.ledger else None
    cwd = Path(args.cwd) if args.cwd else None
    output_dir = Path(args.output_dir) if args.output_dir else None

    if workspace_root is not None:
        workspace_harnessfile = workspace_root / DEFAULT_WORKSPACE_HARNESS
        workspace_registry = workspace_root / DEFAULT_WORKSPACE_REGISTRY
        if harnessfile is None and workspace_harnessfile.exists():
            harnessfile = workspace_harnessfile
        if not registry_paths and workspace_registry.exists():
            registry_paths.append(workspace_registry)
        if ledger_path is None:
            ledger_path = workspace_root / DEFAULT_WORKSPACE_AGENT_RUN_LEDGER
        if cwd is None:
            cwd = workspace_root
        if output_dir is None:
            output_dir = workspace_root / DEFAULT_WORKSPACE_AGENT_RUNS_DIR

    if ledger_path is None:
        print("ERROR: --ledger is required unless --workspace is provided.", file=sys.stderr)
        return 1

    manifest = None
    if harnessfile:
        manifest, status = _load_valid_manifest(harnessfile)
        if status != 0 or manifest is None:
            return status

    try:
        report = run_agent_under_control(
            agent_id=args.agent_id,
            action=args.action,
            target=args.target,
            ledger_path=ledger_path,
            registry_paths=tuple(registry_paths),
            manifest=manifest,
            manifest_source=str(harnessfile) if harnessfile else None,
            requested_risk=args.risk,
            approvals=tuple(args.approval or ()),
            evidence=tuple(args.evidence or ()),
            execute=args.execute,
            confirm=args.confirm,
            cwd=cwd,
            output_dir=output_dir,
            timeout_seconds=args.timeout_seconds,
        )
    except (OSError, ValueError, json.JSONDecodeError, PlanError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_agent_run_report(report))
    return 1 if report.blocked else 0


def cmd_agent_gate(args: argparse.Namespace) -> int:
    harnessfile, agent_id = _resolve_agent_gate_positionals(args.harnessfile_or_agent, args.agent_id)
    if not agent_id:
        print("ERROR: agent-gate needs an agent id.", file=sys.stderr)
        return 1
    if args.write and not args.ledger:
        print("ERROR: agent-gate --write requires --ledger.", file=sys.stderr)
        return 1

    manifest = None
    if harnessfile:
        manifest, status = _load_valid_manifest(Path(harnessfile))
        if status != 0 or manifest is None:
            return status

    report = build_agent_gate_report(
        agent_id=agent_id,
        action=args.action,
        target=args.target,
        manifest=manifest,
        manifest_source=harnessfile,
        registry_paths=tuple(Path(path) for path in args.registry or ()),
        requested_risk=args.risk,
        provided_evidence=tuple(args.evidence or ()),
        provided_approvals=tuple(args.approval or ()),
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_agent_gate_report(report))
    if args.write and args.ledger:
        ledger_path = Path(args.ledger)
        try:
            existing_events = load_jsonl(ledger_path) if ledger_path.exists() else []
            run_id = str(existing_events[0].get("run_id")) if existing_events else f"agent-gate-{agent_id}"
            events = build_agent_gate_events(
                report,
                run_id=run_id,
                start_sequence=len(existing_events) + 1,
            )
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            append_jsonl(events, ledger_path)
        except (EvalError, OSError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if not args.json:
            print(f"\nAgent Gate event appended: {ledger_path}")
    return 1 if report.blocked else 0


def cmd_action_request(args: argparse.Namespace) -> int:
    workspace_root = Path(args.workspace).resolve() if args.workspace else None
    harnessfile = Path(args.harnessfile) if args.harnessfile else None
    registry_paths = [Path(path) for path in args.registry or ()]
    ledger_path = Path(args.ledger) if args.ledger else None

    if workspace_root is not None:
        workspace_harnessfile = workspace_root / DEFAULT_WORKSPACE_HARNESS
        workspace_registry = workspace_root / DEFAULT_WORKSPACE_REGISTRY
        if harnessfile is None and workspace_harnessfile.exists():
            harnessfile = workspace_harnessfile
        if not registry_paths and workspace_registry.exists():
            registry_paths.append(workspace_registry)
        if ledger_path is None:
            ledger_path = workspace_root / DEFAULT_WORKSPACE_AGENT_RUN_LEDGER

    if ledger_path is None:
        print("ERROR: --ledger is required unless --workspace is provided.", file=sys.stderr)
        return 1

    manifest = None
    if harnessfile:
        manifest, status = _load_valid_manifest(harnessfile)
        if status != 0 or manifest is None:
            return status

    try:
        existing_events = load_jsonl(ledger_path) if ledger_path.exists() else []
        report = build_action_request_report(
            agent_id=args.agent_id,
            action=args.action,
            target=args.target,
            ledger_source=str(ledger_path),
            manifest=manifest,
            manifest_source=str(harnessfile) if harnessfile else None,
            registry_paths=tuple(registry_paths),
            requested_risk=args.risk,
            provided_evidence=tuple(args.evidence or ()),
            provided_approvals=tuple(args.approval or ()),
            requested_by=args.requested_by,
            summary=args.summary,
            wrote_ledger=not args.dry_run,
        )
        if not args.dry_run:
            run_id = str(existing_events[0].get("run_id")) if existing_events else f"action-request-{args.agent_id}"
            events = build_action_request_events(
                report,
                run_id=run_id,
                start_sequence=len(existing_events) + 1,
            )
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            append_jsonl(events, ledger_path)
    except (EvalError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_action_request_report(report))
        if not args.dry_run:
            print(f"\nAction request appended: {ledger_path}")
    return 0


def cmd_agent_audit(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger)
    try:
        ledger_events = load_jsonl(ledger_path)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report = build_agent_gate_audit_report(ledger_events, ledger_source=str(ledger_path))
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_agent_gate_audit_report(report))
    return 1 if report.blocked else 0


def cmd_approval_inbox(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger)
    try:
        ledger_events = load_jsonl(ledger_path)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report = build_approval_inbox_report(ledger_events, ledger_source=str(ledger_path))
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_approval_inbox_report(report))
    return 0


def cmd_approval_decision(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger)
    try:
        ledger_events = load_jsonl(ledger_path)
        events = build_approval_decision_events(
            ledger_events,
            action_id=args.action_id,
            decision=args.decision,
            approver=args.approver,
            reason=args.reason or "",
        )
        append_jsonl(events, ledger_path)
    except (EvalError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    receipt = build_approval_decision_receipt(events[0], ledger_source=str(ledger_path))
    if args.json:
        print(json.dumps(receipt.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_approval_decision_receipt(receipt))
        print(f"\nApproval decision appended: {ledger_path}")
    return 0


def cmd_runprint_ingest(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger)
    try:
        ledger_events = load_jsonl(ledger_path)
        bundle = load_runprint_bundle(Path(args.bundle)) if args.bundle else None
        events = build_runprint_recording_events(
            ledger_events,
            action_id=args.action_id,
            recording_id=args.recording_id,
            evidence_bundle_id=args.bundle_id,
            artifacts=artifacts_from_values(tuple(args.artifact or ())),
            summary=args.summary or "",
            source=args.source or (str(args.bundle) if args.bundle else ""),
            bundle=bundle,
        )
        append_jsonl(events, ledger_path)
    except (EvalError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    receipt = build_runprint_ingest_receipt(events[0], ledger_source=str(ledger_path))
    if args.json:
        print(json.dumps(receipt.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_runprint_ingest_receipt(receipt))
        print(f"\nRunPrint evidence appended: {ledger_path}")
    return 0


def cmd_evidence_ingest(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger)
    try:
        ledger_events = load_jsonl(ledger_path)
        bundle = load_evidence_bundle(Path(args.bundle)) if args.bundle else None
        events = build_evidence_recording_events(
            ledger_events,
            evidence_tool=args.tool,
            tool_kind=args.tool_kind,
            action_id=args.action_id,
            recording_id=args.recording_id,
            evidence_bundle_id=args.bundle_id,
            artifacts=evidence_artifacts_from_values(tuple(args.artifact or ())),
            summary=args.summary or "",
            source=args.source or (str(args.bundle) if args.bundle else ""),
            bundle=bundle,
        )
        append_jsonl(events, ledger_path)
    except (EvalError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    receipt = build_evidence_ingest_receipt(events[0], ledger_source=str(ledger_path))
    if args.json:
        print(json.dumps(receipt.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_evidence_ingest_receipt(receipt))
        print(f"\nEvidence appended: {ledger_path}")
    return 0


def cmd_mission_status(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger)
    try:
        ledger_events = load_jsonl(ledger_path)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report = build_mission_status_report(ledger_events, ledger_source=str(ledger_path))
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_mission_status_report(report))
    return 1 if report.blocked else 0


def cmd_agent_packet(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger)
    try:
        ledger_events = load_jsonl(ledger_path)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report = build_agent_packet_report(
        ledger_events,
        action_id=args.action_id,
        ledger_source=str(ledger_path),
    )
    data = report.to_dict()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(render_agent_packet_report(report))
        if args.output:
            print(f"\nAgent packet written: {args.output}")
    return 1 if report.blocked else 0


def cmd_agent_result_ingest(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger)
    result_path = Path(args.result)
    try:
        ledger_events = load_jsonl(ledger_path)
        result = load_agent_result(result_path)
        report = build_agent_result_ingest_report(
            ledger_events,
            result=result,
            result_source=str(result_path),
            ledger_source=str(ledger_path),
            action_id=args.action_id,
        )
        if report.events:
            append_jsonl(report.events, ledger_path)
    except (EvalError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_agent_result_ingest_report(report))
        if report.events:
            print(f"\nAgent result appended: {ledger_path}")
    return 1 if report.blocked else 0


def _resolve_agent_gate_positionals(first: str | None, second: str | None) -> tuple[str | None, str | None]:
    if second:
        return first, second
    if not first:
        return None, None
    candidate = Path(first)
    if candidate.exists() or candidate.suffix.lower() in {".yaml", ".yml", ".json"}:
        return first, None
    return None, first


def cmd_suggest(args: argparse.Namespace) -> int:
    try:
        if args.draft_source == "fixture":
            if not args.provider:
                print("ERROR: --provider is required when --draft-source fixture is used", file=sys.stderr)
                return 1
            if args.provider not in FIXTURE_PROVIDERS:
                print(
                    "ERROR: no-network fixtures are available only for: " + ", ".join(FIXTURE_PROVIDERS),
                    file=sys.stderr,
                )
                return 1
            template_id = args.template or infer_template(args.goal)[0]
            draft = load_model_suggestion_fixture(args.provider, template_id)
            source_name = draft.source_path.name if draft.source_path else "fixture"
            suggestion = HarnessSuggestion(
                goal=draft.goal,
                template_id=draft.template_id,
                template_reason=f"No-network {draft.provider} model fixture loaded from `{source_name}`.",
                manifest=draft.manifest,
            )
        elif args.draft_source == "model":
            if not args.provider:
                print("ERROR: --provider is required when --draft-source model is used", file=sys.stderr)
                return 1
            if args.provider not in LIVE_PROVIDERS:
                print("ERROR: live model providers are: " + ", ".join(LIVE_PROVIDERS), file=sys.stderr)
                return 1
            if not args.allow_live_model:
                print(
                    "ERROR: live model suggestions are opt-in. Add --allow-live-model to confirm "
                    "you want a provider API call or local model server request.",
                    file=sys.stderr,
                )
                return 1
            config = build_live_model_config(
                args.provider,
                model=args.model,
                timeout_seconds=args.timeout_seconds,
                max_output_tokens=args.max_output_tokens,
                base_url=args.base_url,
            )
            draft = fetch_live_model_suggestion(
                args.goal,
                config=config,
                repository=args.repository,
                owner=args.owner,
                template=args.template,
            )
            suggestion = HarnessSuggestion(
                goal=draft.goal,
                template_id=draft.template_id,
                template_reason=f"Live {draft.provider} model draft from `{draft.model}`. {draft.rationale}",
                manifest=draft.manifest,
            )
        else:
            suggestion = build_suggestion(
                args.goal,
                repository=args.repository,
                owner=args.owner,
                template=args.template,
            )
        manifest_yaml = manifest_to_yaml(suggestion.manifest)
    except (RuntimeError, ValueError, ModelSuggestionFixtureError, LiveModelSuggestionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors = suggestion.validate()
    if errors:
        print("INVALID suggested Harnessfile", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(manifest_yaml, encoding="utf-8")

    if args.json:
        print(json.dumps(suggestion.manifest, indent=2, sort_keys=True))
    elif args.yaml and not output_path:
        print(manifest_yaml)
    else:
        print(render_suggestion(suggestion, output_path=str(output_path) if output_path else None))
        if not output_path and not args.plan:
            print("\nTip: add `--output .delegation/suggested.yaml --plan` to write and dry-run it.")
            print("Use `--yaml` when you want the full Harnessfile in the terminal.")

    if args.plan:
        try:
            plan = compile_plan(
                suggestion.manifest,
                source=str(output_path) if output_path else "<suggestion>",
            )
        except PlanError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

        print("\n" + render_plan(plan))
        if args.ledger:
            events = build_dry_run_ledger(plan)
            write_jsonl(events, Path(args.ledger))
            print(f"\nLedger written: {args.ledger}")
    elif args.ledger:
        print("ERROR: --ledger requires --plan", file=sys.stderr)
        return 1

    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    manifest, status = _load_valid_manifest(Path(args.harnessfile))
    if status != 0 or manifest is None:
        return status

    try:
        ledger_events = load_ledger(Path(args.ledger))
    except PromotionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    decisions = evaluate_promotions(manifest, ledger_events)
    if args.json:
        print(json.dumps([decision.to_dict() for decision in decisions], indent=2, sort_keys=True))
    else:
        print(render_promotion_report(decisions))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    if args.feedback_write and not args.feedback:
        print("ERROR: --feedback-write requires --feedback", file=sys.stderr)
        return 1

    manifest, status = _load_valid_manifest(Path(args.harnessfile))
    if status != 0 or manifest is None:
        return status

    ledger_path = Path(args.ledger)
    try:
        ledger_events = load_jsonl(ledger_path)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    results = run_declared_evals(manifest, ledger_events)
    feedback_drafts = []
    if args.feedback:
        try:
            feedback_drafts = build_feedback_issue_drafts_from_results(
                manifest,
                results,
                repository=args.feedback_repository,
                ledger_events=ledger_events,
                ledger_source=str(ledger_path),
                include_blocked=args.feedback_include_blocked,
                blocked_repeat_threshold=args.feedback_blocked_repeat_threshold,
            )
        except (LookupError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if args.json:
        if args.feedback:
            print(
                json.dumps(
                    {
                        "evals": [result.to_dict() for result in results],
                        "feedback_issue_drafts": [draft.to_dict() for draft in feedback_drafts],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(json.dumps([result.to_dict() for result in results], indent=2, sort_keys=True))
    else:
        print(render_eval_report(results))
        if args.feedback:
            print("\n" + render_feedback_report(feedback_drafts))

    if args.write:
        run_id = str(ledger_events[0].get("run_id")) if ledger_events else "eval-run"
        result_events = eval_results_to_events(results, run_id=run_id, start_sequence=len(ledger_events) + 1)
        try:
            append_jsonl(result_events, ledger_path)
        except EvalError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"\nEval events appended: {ledger_path}")
        ledger_events = [*ledger_events, *[event.to_dict() for event in result_events]]

    if args.feedback_write and feedback_drafts:
        run_id = str(ledger_events[0].get("run_id")) if ledger_events else "feedback-run"
        result_events = feedback_drafts_to_events(
            feedback_drafts,
            run_id=run_id,
            start_sequence=len(ledger_events) + 1,
        )
        try:
            append_feedback_events(result_events, ledger_path)
        except OSError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"\nFeedback issue events appended: {ledger_path}")
    return 0


def cmd_feedback(args: argparse.Namespace) -> int:
    manifest, status = _load_valid_manifest(Path(args.harnessfile))
    if status != 0 or manifest is None:
        return status

    ledger_path = Path(args.ledger)
    try:
        ledger_events = load_jsonl(ledger_path)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        drafts = build_feedback_issue_drafts(
            manifest,
            ledger_events,
            repository=args.repository,
            ledger_source=str(ledger_path),
            include_blocked=args.include_blocked,
            blocked_repeat_threshold=args.blocked_repeat_threshold,
        )
    except (LookupError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps([draft.to_dict() for draft in drafts], indent=2, sort_keys=True))
    else:
        print(render_feedback_report(drafts))

    if args.write and drafts:
        run_id = str(ledger_events[0].get("run_id")) if ledger_events else "feedback-run"
        result_events = feedback_drafts_to_events(
            drafts,
            run_id=run_id,
            start_sequence=len(ledger_events) + 1,
        )
        try:
            append_feedback_events(result_events, ledger_path)
        except OSError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"\nFeedback issue events appended: {ledger_path}")
    return 0


def cmd_recover_feedback(args: argparse.Namespace) -> int:
    manifest, status = _load_valid_manifest(Path(args.harnessfile))
    if status != 0 or manifest is None:
        return status

    ledger_path = Path(args.ledger)
    try:
        ledger_events = load_jsonl(ledger_path)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        drafts = build_feedback_resolution_drafts(
            manifest,
            ledger_events,
            repository=args.repository,
            ledger_source=str(ledger_path),
        )
    except (LookupError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps([draft.to_dict() for draft in drafts], indent=2, sort_keys=True))
    else:
        print(render_feedback_report(drafts))

    if args.write and drafts:
        run_id = str(ledger_events[0].get("run_id")) if ledger_events else "feedback-recovery-run"
        result_events = feedback_drafts_to_events(
            drafts,
            run_id=run_id,
            start_sequence=len(ledger_events) + 1,
        )
        try:
            append_feedback_events(result_events, ledger_path)
        except OSError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"\nFeedback recovery events appended: {ledger_path}")
    return 0


def _blocked_non_token_gates(report: T.Any) -> list[str]:
    return [
        gate.id
        for gate in getattr(report, "gates", ())
        if getattr(gate, "status", None) == "blocked" and getattr(gate, "id", "") != "github.token"
    ]


def _issue_report_repositories(report: T.Any) -> list[str]:
    repositories: list[str] = []
    for draft in getattr(report, "drafts", ()):
        repository = getattr(draft, "repository", None)
        if isinstance(repository, str) and repository.strip():
            repositories.append(repository)
            continue
        adapter_result = getattr(draft, "adapter_result", None)
        outputs = getattr(adapter_result, "outputs", {}) if adapter_result is not None else {}
        issue = outputs.get("github.issue") if isinstance(outputs, dict) else {}
        if isinstance(issue, dict) and isinstance(issue.get("repository"), str) and issue["repository"].strip():
            repositories.append(issue["repository"])
    return sorted(set(repositories))


def _resolve_issue_auth(args: argparse.Namespace, report: T.Any) -> GitHubAuthResolution:
    repositories = _issue_report_repositories(report)
    if not args.apply:
        return resolve_github_auth_token(
            mode=args.auth,
            apply=False,
            repositories=(),
            permissions=ISSUE_WRITE_PERMISSIONS,
        )
    if not repositories:
        return GitHubAuthResolution(
            mode=args.auth,
            status="preview",
            message="No GitHub issue write is planned, so no token was minted.",
        )
    blocked_non_token = _blocked_non_token_gates(report)
    if blocked_non_token and args.auth in (AUTH_AUTO, AUTH_GITHUB_APP):
        return GitHubAuthResolution(
            mode=args.auth,
            status="blocked",
            message="GitHub auth was not resolved because another apply gate is blocked.",
            next_action=f"Fix blocked gates first: {', '.join(blocked_non_token)}.",
        )
    return resolve_github_auth_token(
        mode=args.auth,
        apply=True,
        repositories=repositories,
        permissions=ISSUE_WRITE_PERMISSIONS,
    )


def _print_report_with_auth(report: T.Any, auth: GitHubAuthResolution, *, json_output: bool, renderer: T.Callable[[T.Any], str]) -> None:
    if json_output:
        data = report.to_dict()
        data["auth"] = auth.to_dict()
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(renderer(report))
    if auth.mode != AUTH_AUTO or auth.status != "preview":
        print("\n" + render_github_auth_resolution(auth))


def cmd_apply_feedback(args: argparse.Namespace) -> int:
    manifest, status = _load_valid_manifest(Path(args.harnessfile))
    if status != 0 or manifest is None:
        return status

    ledger_path = Path(args.ledger)
    try:
        ledger_events = load_jsonl(ledger_path)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        report = build_feedback_apply_report(
            manifest,
            ledger_events,
            ledger_source=str(ledger_path),
            repository=args.repository,
            apply=args.apply,
            close=args.close,
            confirmation=args.confirm,
            token=None if args.auth == AUTH_GITHUB_APP else github_token_from_env(),
        )
    except (LookupError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    auth = _resolve_issue_auth(args, report)
    if auth.token_value:
        report = build_feedback_apply_report(
            manifest,
            ledger_events,
            ledger_source=str(ledger_path),
            repository=args.repository,
            apply=args.apply,
            close=args.close,
            confirmation=args.confirm,
            token=auth.token_value,
        )

    _print_report_with_auth(report, auth, json_output=args.json, renderer=render_feedback_apply_report)

    if report.blocked or auth.blocked:
        return 1
    if not args.apply or not report.drafts:
        return 0

    run_id = str(ledger_events[0].get("run_id")) if ledger_events else "feedback-apply-run"
    events = apply_feedback_resolution_drafts(
        report.drafts,
        client=GitHubIssueClient(auth.token_value or ""),
        run_id=run_id,
        start_sequence=len(ledger_events) + 1,
        close=args.close,
        auth_source=auth.source,
    )
    try:
        append_jsonl(events, ledger_path)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not args.json:
        print(f"\nFeedback apply events appended: {ledger_path}")
    return 1 if any(event.status == "failed" for event in events) else 0


def cmd_adapters(args: argparse.Namespace) -> int:
    if args.adapter_id:
        contract = get_adapter_contract(args.adapter_id)
        if not contract:
            print(f"ERROR: unknown adapter contract `{args.adapter_id}`", file=sys.stderr)
            return 1
        contracts = [contract]
    else:
        contracts = list_adapter_contracts()

    if args.json:
        print(json.dumps([contract.to_dict() for contract in contracts], indent=2, sort_keys=True))
    else:
        print(render_adapter_contracts(contracts))
    return 0


def cmd_ledger(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger)
    try:
        events = load_ledger_events(ledger_path)
    except LedgerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    ledger_filter = LedgerFilter(
        event_type=args.event_type,
        status=args.status,
        action_id=args.action,
        adapter=args.adapter,
    )
    view = build_ledger_view(events, source=str(ledger_path), ledger_filter=ledger_filter, limit=args.limit)
    if args.json:
        print(json.dumps(view.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_ledger_view(view))
    return 0


def cmd_evidence(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger)
    try:
        events = load_ledger_events(ledger_path)
    except LedgerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report = build_evidence_report(events, source=str(ledger_path))
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_evidence_report(report))
    return 0


def cmd_explain_policy(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger)
    try:
        events = load_ledger_events(ledger_path)
        config = None
        if args.draft_source == "model":
            if args.provider != "ollama":
                print("ERROR: policy explanations currently support the local `ollama` provider only", file=sys.stderr)
                return 1
            config = build_live_model_config(
                args.provider,
                model=args.model,
                timeout_seconds=args.timeout_seconds,
                max_output_tokens=args.max_output_tokens,
                base_url=args.base_url,
            )
        report = build_policy_explanation_report(
            events,
            ledger_source=str(ledger_path),
            use_model=args.draft_source == "model",
            allow_live_model=args.allow_live_model,
            config=config,
        )
    except (LedgerError, LiveModelSuggestionError, PolicyExplainError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_policy_explanation_report(report))
    return 1 if report.blocked else 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger)
    try:
        events = load_ledger_events(ledger_path)
    except LedgerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    manifest = None
    if args.harnessfile:
        manifest, status = _load_valid_manifest(Path(args.harnessfile))
        if status != 0 or manifest is None:
            return status

    snapshot = build_dashboard_snapshot(events, manifest=manifest, source=str(ledger_path))
    if args.json:
        print(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_dashboard_snapshot(snapshot))
    return 0


def cmd_otel(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger)
    try:
        events = load_ledger_events(ledger_path)
        export = build_otel_export(events, source=str(ledger_path), environment=args.environment)
    except (LedgerError, OtelExportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.output:
        try:
            write_otel_export(export, Path(args.output))
        except OSError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if args.json:
        print(json.dumps(export.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_otel_export(export))
        if args.output:
            print(f"\nOpenTelemetry JSON written: {args.output}")
    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    catalog_path = Path(args.catalog)
    try:
        catalog = load_catalog(catalog_path)
        errors = validate_catalog(catalog, catalog_path.resolve().parents[1])
    except (OSError, json.JSONDecodeError, PlaybookCatalogError, ManifestError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        print("INVALID Playbook catalog", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    filtered_catalog, catalog_filter = filter_catalog(
        catalog,
        tags=args.tag,
        adapters=args.adapter,
    )
    if args.list_tags or args.list_adapters:
        facets = catalog_facets(catalog)
        if args.json:
            output = {}
            if args.list_tags:
                output["tags"] = facets["tags"]
            if args.list_adapters:
                output["adapters"] = facets["adapters"]
            print(json.dumps(output, indent=2, sort_keys=True))
            return 0
        lines: list[str] = []
        if args.list_tags:
            lines.extend(["Catalog tags", "", *[f"- {tag}" for tag in facets["tags"]]])
        if args.list_adapters:
            if lines:
                lines.append("")
            lines.extend(["Catalog adapters", "", *[f"- {adapter}" for adapter in facets["adapters"]]])
        print("\n".join(lines))
        return 0

    if args.json:
        print(json.dumps(filtered_catalog, indent=2, sort_keys=True))
    else:
        print(summarize_catalog(filtered_catalog, catalog_filter=catalog_filter))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    report = run_doctor(include_github=not args.skip_github, include_github_app=args.github_app)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_doctor_report(report))
    return 1 if report.failed_count else 0


def cmd_apply_issues(args: argparse.Namespace) -> int:
    path = Path(args.harnessfile)
    manifest, status = _load_valid_manifest(path)
    if status != 0 or manifest is None:
        return status

    try:
        plan = compile_plan(manifest, source=str(path))
    except PlanError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    ledger_path = Path(args.ledger)
    try:
        ledger_events = load_jsonl(ledger_path)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report = build_apply_report(
        manifest,
        plan,
        ledger_events,
        ledger_source=str(ledger_path),
        apply=args.apply,
        confirmation=args.confirm,
        token=None if args.auth == AUTH_GITHUB_APP else github_token_from_env(),
    )
    auth = _resolve_issue_auth(args, report)
    if auth.token_value:
        report = build_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=str(ledger_path),
            apply=args.apply,
            confirmation=args.confirm,
            token=auth.token_value,
        )

    _print_report_with_auth(report, auth, json_output=args.json, renderer=render_apply_report)

    if report.blocked or auth.blocked:
        return 1

    if not args.apply:
        return 0

    run_id = str(ledger_events[0].get("run_id")) if ledger_events else f"apply-{plan.id}"
    events = apply_github_issue_drafts(
        report.drafts,
        client=GitHubIssueClient(auth.token_value or ""),
        run_id=run_id,
        start_sequence=len(ledger_events) + 1,
        auth_source=auth.source,
    )
    try:
        append_jsonl(events, ledger_path)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not args.json:
        print(f"\nApply events appended: {ledger_path}")
    return 1 if any(event.status == "failed" for event in events) else 0


def cmd_apply_actions(args: argparse.Namespace) -> int:
    path = Path(args.harnessfile)
    manifest, status = _load_valid_manifest(path)
    if status != 0 or manifest is None:
        return status

    try:
        plan = compile_plan(manifest, source=str(path))
    except PlanError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    ledger_path = Path(args.ledger)
    try:
        ledger_events = load_jsonl(ledger_path)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    token = github_token_from_env()
    actions_client = GitHubActionsClient(token) if args.apply and token else None
    report = build_actions_apply_report(
        manifest,
        plan,
        ledger_events,
        ledger_source=str(ledger_path),
        apply=args.apply,
        confirmation=args.confirm,
        token=token,
        preflight_client=actions_client,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_actions_apply_report(report))

    if report.blocked:
        return 1

    if not args.apply:
        return 0

    run_id = str(ledger_events[0].get("run_id")) if ledger_events else f"apply-{plan.id}"
    events = apply_github_actions_drafts(
        report.drafts,
        client=actions_client or GitHubActionsClient(token or ""),
        run_id=run_id,
        start_sequence=len(ledger_events) + 1,
    )
    try:
        append_jsonl(events, ledger_path)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not args.json:
        print(f"\nDispatch events appended: {ledger_path}")
    return 1 if any(event.status == "failed" for event in events) else 0


def cmd_cancel_actions(args: argparse.Namespace) -> int:
    token = github_token_from_env()
    actions_client = GitHubActionsClient(token) if args.apply and token else None
    token_diagnostics: GitHubTokenDiagnostics | None = None
    required_confirmation = FORCE_CANCEL_CONFIRMATION if args.force else CANCEL_CONFIRMATION
    if args.apply and actions_client and args.confirm == required_confirmation:
        try:
            token_diagnostics = actions_client.inspect_token()
        except Exception as exc:  # pragma: no cover - network failures are environment-specific
            token_diagnostics = GitHubTokenDiagnostics(available=False, note=str(exc))

    report = build_actions_cancel_report(
        args.repository,
        args.run_id,
        apply=args.apply,
        force=args.force,
        confirmation=args.confirm,
        token=token,
        token_diagnostics=token_diagnostics,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_actions_cancel_report(report))

    if report.blocked:
        return 1

    if not args.apply:
        return 0

    existing_events: list[dict[str, T.Any]] = []
    ledger_path = Path(args.ledger) if args.ledger else None
    if ledger_path and ledger_path.exists():
        try:
            existing_events = load_jsonl(ledger_path)
        except EvalError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    ledger_run_id = str(existing_events[0].get("run_id")) if existing_events else f"github-actions-cancel-{args.run_id}"
    events = cancel_github_actions_run(
        report.target,
        client=actions_client or GitHubActionsClient(token or ""),
        run_id=ledger_run_id,
        start_sequence=len(existing_events) + 1,
    )
    if ledger_path:
        try:
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            append_jsonl(events, ledger_path)
        except (EvalError, OSError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if not args.json:
            print(f"\nCancel events appended: {ledger_path}")
    elif not args.json:
        print("\nCancel events were not appended because no --ledger path was provided.")
    return 1 if any(event.status == "failed" for event in events) else 0


def cmd_mcp_gate(args: argparse.Namespace) -> int:
    path = Path(args.harnessfile)
    manifest, status = _load_valid_manifest(path)
    if status != 0 or manifest is None:
        return status

    try:
        plan = compile_plan(manifest, source=str(path))
    except PlanError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    ledger_path = Path(args.ledger)
    try:
        ledger_events = load_jsonl(ledger_path)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report = build_mcp_policy_report(
        manifest,
        plan,
        ledger_events,
        ledger_source=str(ledger_path),
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_mcp_policy_report(report))
    return 1 if report.blocked else 0


def cmd_release_check(args: argparse.Namespace) -> int:
    report = build_release_readiness_report(strict_artifacts=args.strict_artifacts)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_release_readiness_report(report))
    return 1 if report.failed_count else 0


def cmd_github_app_plan(args: argparse.Namespace) -> int:
    try:
        plan = build_github_app_plan(args.mode, repository=args.repository)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.output:
        try:
            write_github_app_plan(plan, Path(args.output))
        except OSError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if args.json:
        print(json.dumps(plan.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_github_app_plan(plan))
        if args.output:
            print(f"\nPlan written: {args.output}")
    return 0


def cmd_artifacts(args: argparse.Namespace) -> int:
    dist_path = Path(args.dist)
    if args.check:
        report = verify_artifact_outputs(dist_path)
        if args.json:
            print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        else:
            print(render_artifact_verification_report(report))
        return 0 if report.ready else 1

    try:
        manifest = write_artifact_outputs(dist_path)
    except ArtifactError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_artifact_manifest(manifest, dist_path=dist_path))
    return 0


def cmd_release_rehearse(args: argparse.Namespace) -> int:
    report = build_release_rehearsal(
        output_dir=Path(args.output),
        dist_path=Path(args.dist),
        strict_artifacts=args.strict_artifacts,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_release_rehearsal_report(report))
    return 1 if report.failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"DelegationHQ {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="Run a safe first-run mission-control demo.")
    demo.add_argument(
        "--ledger",
        default=DEFAULT_DEMO_LEDGER,
        help="Write the demo dry-run ledger to this JSONL path.",
    )
    demo.add_argument(
        "--harnessfile",
        help="Use a Harnessfile instead of the built-in install-safe demo mission.",
    )
    demo.add_argument(
        "--repository",
        default="AmmarAlBalkhi/delegation-bot",
        help="Repository owner/name to use in the built-in demo.",
    )
    demo.add_argument("--owner", default="maintainer", help="Accountable owner/reviewer for the built-in demo.")
    demo.add_argument(
        "--control-loop",
        action="store_true",
        help="Append a full Agent Gate -> approval -> RunPrint -> audit receipt chain.",
    )
    demo.add_argument("--control-agent", help="Agent id for --control-loop. Defaults to the built-in demo agent.")
    demo.add_argument("--control-action", help="Requested action for --control-loop.")
    demo.add_argument("--control-target", help="Target resource for --control-loop.")
    demo.add_argument("--approver", help="Approver name for the demo approval receipt. Defaults to --owner.")
    demo.add_argument("--json", action="store_true", help="Print the demo report as JSON.")
    demo.set_defaults(func=cmd_demo)

    init = subparsers.add_parser("init", help="Create a starter Harnessfile for this repository.")
    init.add_argument("--goal", default=DEFAULT_INIT_GOAL, help="Plain-language mission goal for the starter Harnessfile.")
    init.add_argument("--output", default=DEFAULT_INIT_OUTPUT, help="Harnessfile path to create.")
    init.add_argument("--repository", help="Repository owner/name. Defaults to GitHub origin when detected.")
    init.add_argument("--owner", help="Accountable owner/reviewer. Defaults to the repository owner.")
    init.add_argument(
        "--template",
        choices=SUGGESTION_TEMPLATE_IDS,
        help="Force a starter template instead of inferring one from the goal.",
    )
    init.add_argument("--force", action="store_true", help="Overwrite the output Harnessfile if it already exists.")
    init.add_argument("--plan", action="store_true", help="Also compile the starter Harnessfile and write a ledger.")
    init.add_argument("--ledger", help="Ledger path for --plan. Defaults to .delegation/init.jsonl.")
    init.add_argument("--json", action="store_true", help="Print the init report as JSON.")
    init.set_defaults(func=cmd_init)

    workspace_init = subparsers.add_parser(
        "workspace-init",
        help="Turn any local folder into a no-GitHub DelegationHQ workspace.",
    )
    workspace_init.add_argument("--path", default=".", help="Workspace folder to initialize. Defaults to the current folder.")
    workspace_init.add_argument("--name", default="Local DelegationHQ Workspace", help="Workspace display name.")
    workspace_init.add_argument(
        "--goal",
        default="control AI work in this local workspace",
        help="Plain-language mission goal for this local workspace.",
    )
    workspace_init.add_argument("--owner", default="local-operator", help="Accountable local owner/reviewer.")
    workspace_init.add_argument("--force", action="store_true", help="Overwrite existing .delegation workspace files.")
    workspace_init.add_argument("--plan", action="store_true", help="Also compile the local Harnessfile and write a ledger.")
    workspace_init.add_argument("--ledger", help="Ledger path for --plan. Defaults to .delegation/local-workspace.jsonl.")
    workspace_init.add_argument("--json", action="store_true", help="Print the workspace init report as JSON.")
    workspace_init.set_defaults(func=cmd_workspace_init)

    workspace_status = subparsers.add_parser(
        "workspace-status",
        help="Show local workspace health without requiring GitHub.",
    )
    workspace_status.add_argument("--path", default=".", help="Workspace folder to inspect. Defaults to the current folder.")
    workspace_status.add_argument("--ledger", help="Optional ledger path. Defaults to .delegation/local-workspace.jsonl.")
    workspace_status.add_argument("--json", action="store_true", help="Print the workspace status as JSON.")
    workspace_status.set_defaults(func=cmd_workspace_status)

    app_plan = subparsers.add_parser(
        "app-plan",
        help="Show the first visible Windows EXE app plan without launching a UI.",
    )
    app_plan.add_argument("--json", action="store_true", help="Print the app plan as JSON.")
    app_plan.set_defaults(func=cmd_app_plan)

    app_state = subparsers.add_parser(
        "app-state",
        help="Show one read-only app-ready state bundle for the future local cockpit.",
    )
    app_state.add_argument("--workspace", help="Optional local workspace folder. Defaults registry and ledger paths from .delegation.")
    app_state.add_argument("--ledger", help="Optional run ledger JSONL path for mission/evidence state.")
    app_state.add_argument("--harnessfile", help="Optional Harnessfile for agent and owner context.")
    app_state.add_argument(
        "--agent-registry",
        action="append",
        help="Optional Agent Passport registry file. Repeatable.",
    )
    app_state.add_argument(
        "--github-checks",
        action="store_true",
        help="Include GitHub CLI/auth checks in the doctor section.",
    )
    app_state.add_argument(
        "--github-app",
        action="store_true",
        help="Include local GitHub App auth diagnostics without minting a token.",
    )
    app_state.add_argument(
        "--strict-artifacts",
        action="store_true",
        help="Mark missing standalone release artifacts as failed in the release section.",
    )
    app_state.add_argument("--json", action="store_true", help="Print the app state as JSON.")
    app_state.add_argument("--gate-agent", help="Optional Agent Gate preview agent id.")
    app_state.add_argument("--gate-action", help="Optional Agent Gate preview action.")
    app_state.add_argument("--gate-target", help="Optional Agent Gate preview target.")
    app_state.add_argument(
        "--gate-risk",
        choices=("low", "medium", "high", "critical"),
        help="Optional Agent Gate requested risk.",
    )
    app_state.add_argument(
        "--gate-approval",
        action="append",
        help="Optional Agent Gate approval evidence. Repeatable.",
    )
    app_state.add_argument(
        "--gate-evidence",
        action="append",
        help="Optional Agent Gate evidence already present. Repeatable.",
    )
    app_state.set_defaults(func=cmd_app_state)

    cockpit = subparsers.add_parser(
        "cockpit",
        help="Show the local workspace cockpit state with app-ready defaults.",
    )
    cockpit.add_argument("--workspace", default=".", help="Local workspace folder. Defaults to the current folder.")
    cockpit.add_argument("--json", action="store_true", help="Print the cockpit state as JSON.")
    cockpit.set_defaults(func=cmd_cockpit)

    app_dashboard = subparsers.add_parser(
        "app-dashboard",
        help="Show the combined local app dashboard bundle for a workspace.",
    )
    app_dashboard.add_argument("--workspace", default=".", help="Local workspace folder. Defaults to the current folder.")
    app_dashboard.add_argument("--preview-agent", help="Agent id to show in the approval preview card.")
    app_dashboard.add_argument("--preview-action", default="read.workspace", help="Approval preview action. Defaults to read.workspace.")
    app_dashboard.add_argument("--preview-target", default="workspace", help="Approval preview target. Defaults to workspace.")
    app_dashboard.add_argument("--preview-note", help="Optional reviewer note to include in the approval preview packet.")
    app_dashboard.add_argument("--preview-expires-at", help="Optional ISO timestamp after which the preview should be regenerated.")
    app_dashboard.add_argument(
        "--preview-risk",
        choices=("low", "medium", "high", "critical"),
        help="Optional approval preview risk override.",
    )
    app_dashboard.add_argument("--json", action="store_true", help="Print the dashboard bundle as JSON.")
    app_dashboard.set_defaults(func=cmd_app_dashboard)

    app_export = subparsers.add_parser(
        "app-export",
        help="Write a static local browser cockpit bundle for a workspace.",
    )
    app_export.add_argument("--workspace", default=".", help="Local workspace folder. Defaults to the current folder.")
    app_export.add_argument("--output", help="Output directory. Defaults to .delegation/cockpit inside the workspace.")
    app_export.add_argument("--preview-agent", help="Agent id to show in the approval preview card.")
    app_export.add_argument("--preview-action", default="read.workspace", help="Approval preview action. Defaults to read.workspace.")
    app_export.add_argument("--preview-target", default="workspace", help="Approval preview target. Defaults to workspace.")
    app_export.add_argument("--preview-note", help="Optional reviewer note to include in the approval preview packet.")
    app_export.add_argument("--preview-expires-at", help="Optional ISO timestamp after which the preview should be regenerated.")
    app_export.add_argument("--json", action="store_true", help="Print the export report as JSON.")
    app_export.set_defaults(func=cmd_app_export)

    app_serve = subparsers.add_parser(
        "app-serve",
        help="Serve the local browser cockpit over http://127.0.0.1.",
    )
    app_serve.add_argument("--workspace", default=".", help="Local workspace folder. Defaults to the current folder.")
    app_serve.add_argument("--host", default=DEFAULT_APP_HOST, help=f"Host to bind. Defaults to {DEFAULT_APP_HOST}.")
    app_serve.add_argument("--port", type=int, default=DEFAULT_APP_PORT, help=f"Port to bind. Defaults to {DEFAULT_APP_PORT}.")
    app_serve.add_argument("--preview-agent", help="Agent id to show in the approval preview card.")
    app_serve.add_argument("--preview-action", default="read.workspace", help="Approval preview action. Defaults to read.workspace.")
    app_serve.add_argument("--preview-target", default="workspace", help="Approval preview target. Defaults to workspace.")
    app_serve.add_argument("--preview-note", help="Optional reviewer note to include in the approval preview packet.")
    app_serve.add_argument("--preview-expires-at", help="Optional ISO timestamp after which the preview should be regenerated.")
    app_serve.add_argument("--dry-run", action="store_true", help="Print the local app URL without starting the server.")
    app_serve.add_argument("--json", action="store_true", help="Print the server report as JSON.")
    app_serve.set_defaults(func=cmd_app_serve)

    approval_preview = subparsers.add_parser(
        "approval-preview",
        help="Show the human approval card for one agent action.",
    )
    approval_preview.add_argument("agent_id", help="Agent id from a Harnessfile or Agent Passport registry.")
    approval_preview.add_argument("--workspace", help="Optional local workspace folder. Defaults registry, harness, and ledger paths.")
    approval_preview.add_argument("--harnessfile", help="Optional Harnessfile with `agents:` declarations.")
    approval_preview.add_argument(
        "--registry",
        action="append",
        help="Optional Agent Passport registry file. Repeatable.",
    )
    approval_preview.add_argument("--ledger", help="Optional ledger path for approval next-actions.")
    approval_preview.add_argument("--action", default="read.workspace", help="Requested action. Defaults to read.workspace.")
    approval_preview.add_argument("--target", default="workspace", help="Target resource, file, tool, or data scope.")
    approval_preview.add_argument(
        "--risk",
        choices=("low", "medium", "high", "critical"),
        help="Optional requested risk override.",
    )
    approval_preview.add_argument("--approval", action="append", help="Approval evidence already present. Repeatable.")
    approval_preview.add_argument("--evidence", action="append", help="Evidence already present. Repeatable.")
    approval_preview.add_argument("--review-note", help="Optional reviewer note to attach to this preview packet.")
    approval_preview.add_argument("--expires-at", help="Optional ISO timestamp after which this preview should be regenerated.")
    approval_preview.add_argument("--json", action="store_true", help="Print the approval preview as JSON.")
    approval_preview.set_defaults(func=cmd_approval_preview)

    timeline = subparsers.add_parser(
        "timeline",
        help="Show mission history as plan, gate, approval, execution, proof, eval, and promotion steps.",
    )
    timeline.add_argument("--workspace", help="Optional local workspace folder. Defaults ledger path from .delegation.")
    timeline.add_argument("--ledger", help="Optional run ledger JSONL path.")
    timeline.add_argument("--limit", type=int, default=20, help="Number of recent timeline items to show; 0 shows all.")
    timeline.add_argument("--json", action="store_true", help="Print the timeline as JSON.")
    timeline.set_defaults(func=cmd_timeline)

    agents = subparsers.add_parser(
        "agents",
        help="Show Agent Passports from a Harnessfile and optional BYOA registry files.",
    )
    agents.add_argument("harnessfile", nargs="?", help="Optional Harnessfile with `agents:` declarations.")
    agents.add_argument(
        "--registry",
        action="append",
        help="Optional Agent Passport registry file. Repeatable.",
    )
    agents.add_argument("--json", action="store_true", help="Print Agent Passports as JSON.")
    agents.set_defaults(func=cmd_agents)

    agent_add = subparsers.add_parser(
        "agent-add",
        help="Register a custom Bring Your Own Agent passport without hand-editing YAML.",
    )
    agent_add.add_argument("agent_id", help="Stable agent id, such as research_agent.")
    agent_add.add_argument("--workspace", help="Optional local workspace folder. Defaults --registry into .delegation/agents.yaml.")
    agent_add.add_argument("--registry", default=DEFAULT_REGISTRY_PATH, help="Agent registry path to create or update.")
    agent_add.add_argument("--name", help="Human-readable agent name.")
    agent_add.add_argument("--runtime-type", default="cli.command", help="Runtime type, such as cli.command, api, webhook, mcp, or langgraph.graph.")
    agent_add.add_argument("--command", help="Command endpoint for local CLI agents.")
    agent_add.add_argument("--api-url", help="API endpoint for a hosted or local HTTP agent.")
    agent_add.add_argument("--webhook-url", help="Webhook endpoint for event-driven agents.")
    agent_add.add_argument("--mcp-endpoint", help="MCP server/tool endpoint for MCP-backed agents.")
    agent_add.add_argument(
        "--autonomy-level",
        choices=("suggest", "draft", "act", "operate", "deploy"),
        default="suggest",
        help="How much freedom the agent starts with.",
    )
    agent_add.add_argument(
        "--risk-level",
        choices=("low", "medium", "high", "critical"),
        default="low",
        help="Starting risk level for the agent passport.",
    )
    agent_add.add_argument("--capability", action="append", help="Capability the agent may use. Repeatable.")
    agent_add.add_argument("--allowed-tool", action="append", help="Tool the agent may touch. Repeatable.")
    agent_add.add_argument("--allowed-data", action="append", help="Data or workspace scope the agent may touch. Repeatable.")
    agent_add.add_argument("--approval", action="append", help="Action that requires approval. Repeatable.")
    agent_add.add_argument("--expected-output", action="append", help="Expected output artifact. Repeatable.")
    agent_add.add_argument("--evidence", action="append", help="Required evidence artifact. Repeatable.")
    agent_add.add_argument("--promotion-eval", action="append", help="Eval required before promotion. Repeatable.")
    agent_add.add_argument("--force", action="store_true", help="Replace an existing agent with the same id.")
    agent_add.add_argument("--json", action="store_true", help="Print the added agent report as JSON.")
    agent_add.set_defaults(func=cmd_agent_add)

    agent_run = subparsers.add_parser(
        "agent-run",
        help="Gate and optionally execute a command-backed custom agent with ledger evidence.",
    )
    agent_run.add_argument("agent_id", help="Agent id from a Harnessfile or Agent Passport registry.")
    agent_run.add_argument("--workspace", help="Optional local workspace folder. Defaults registry, ledger, cwd, and evidence output paths.")
    agent_run.add_argument("--harnessfile", help="Optional Harnessfile with `agents:` declarations.")
    agent_run.add_argument(
        "--registry",
        action="append",
        help="Optional Agent Passport registry file. Repeatable.",
    )
    agent_run.add_argument("--ledger", help="Read and append run ledger JSONL evidence. Defaults to workspace .delegation/agent-run.jsonl.")
    agent_run.add_argument("--action", default="read.workspace", help="Requested action. Defaults to read.workspace.")
    agent_run.add_argument("--target", default="workspace", help="Target resource, file, tool, or data scope. Defaults to workspace.")
    agent_run.add_argument(
        "--risk",
        choices=("low", "medium", "high", "critical"),
        help="Optional requested risk override.",
    )
    agent_run.add_argument("--approval", action="append", help="Approval evidence already present. Repeatable.")
    agent_run.add_argument("--evidence", action="append", help="Evidence already present. Repeatable.")
    agent_run.add_argument(
        "--execute",
        action="store_true",
        help="Actually run a command-backed agent after the gate allows it.",
    )
    agent_run.add_argument(
        "--confirm",
        help=f"Required exact token for --execute: {LOCAL_AGENT_EXECUTION_CONFIRMATION}.",
    )
    agent_run.add_argument("--cwd", help="Working directory for command execution. Defaults to current folder.")
    agent_run.add_argument("--output-dir", help="Directory for command output evidence JSON.")
    agent_run.add_argument(
        "--timeout-seconds",
        type=int,
        default=AGENT_RUN_DEFAULT_TIMEOUT_SECONDS,
        help="Maximum command runtime in seconds.",
    )
    agent_run.add_argument("--json", action="store_true", help="Print the agent run report as JSON.")
    agent_run.set_defaults(func=cmd_agent_run)

    agent_gate = subparsers.add_parser(
        "agent-gate",
        help="Preview whether an Agent Passport can perform a requested action.",
    )
    agent_gate.add_argument(
        "harnessfile_or_agent",
        nargs="?",
        help="Harnessfile path, or the agent id when using only --registry.",
    )
    agent_gate.add_argument("agent_id", nargs="?", help="Agent id when a Harnessfile path is provided.")
    agent_gate.add_argument(
        "--registry",
        action="append",
        help="Optional Agent Passport registry file. Repeatable.",
    )
    agent_gate.add_argument("--action", required=True, help="Requested action, such as create_pull_request.")
    agent_gate.add_argument("--target", required=True, help="Target resource, file, tool, or data scope.")
    agent_gate.add_argument(
        "--risk",
        choices=("low", "medium", "high", "critical"),
        help="Optional requested risk override.",
    )
    agent_gate.add_argument(
        "--approval",
        action="append",
        help="Approval evidence already present for this preview. Repeatable.",
    )
    agent_gate.add_argument(
        "--evidence",
        action="append",
        help="Evidence already present for this preview. Repeatable.",
    )
    agent_gate.add_argument("--ledger", help="Optional ledger path for appending Agent Gate evidence.")
    agent_gate.add_argument(
        "--write",
        action="store_true",
        help="Append this Agent Gate preview as a JSONL ledger event. Requires --ledger.",
    )
    agent_gate.add_argument("--json", action="store_true", help="Print the Agent Gate report as JSON.")
    agent_gate.set_defaults(func=cmd_agent_gate)

    action_request = subparsers.add_parser(
        "action-request",
        help="Submit an agent action request and create the matching gate receipt.",
    )
    action_request.add_argument("agent_id", help="Agent id from a Harnessfile or Agent Passport registry.")
    action_request.add_argument("--workspace", help="Optional local workspace folder. Defaults registry, harness, and ledger paths.")
    action_request.add_argument("--harnessfile", help="Optional Harnessfile with `agents:` declarations.")
    action_request.add_argument(
        "--registry",
        action="append",
        help="Optional Agent Passport registry file. Repeatable.",
    )
    action_request.add_argument("--ledger", help="Append the request to this run ledger JSONL file.")
    action_request.add_argument("--action", required=True, help="Requested action, such as update.crm_record.")
    action_request.add_argument("--target", required=True, help="Target resource, file, tool, or data scope.")
    action_request.add_argument(
        "--risk",
        choices=("low", "medium", "high", "critical"),
        help="Optional requested risk override.",
    )
    action_request.add_argument("--approval", action="append", help="Approval evidence already present. Repeatable.")
    action_request.add_argument("--evidence", action="append", help="Evidence already present. Repeatable.")
    action_request.add_argument("--requested-by", help="Who submitted the request. Defaults to the agent id.")
    action_request.add_argument("--summary", help="Short human-readable request summary.")
    action_request.add_argument("--dry-run", action="store_true", help="Preview without writing request receipts.")
    action_request.add_argument("--json", action="store_true", help="Print the action request receipt as JSON.")
    action_request.set_defaults(func=cmd_action_request)

    agent_audit = subparsers.add_parser(
        "agent-audit",
        help="Compare Agent Gate intent receipts with recorded evidence in a ledger.",
    )
    agent_audit.add_argument("--ledger", required=True, help="Read run ledger JSONL evidence.")
    agent_audit.add_argument("--json", action="store_true", help="Print the Agent Gate audit report as JSON.")
    agent_audit.set_defaults(func=cmd_agent_audit)

    approval_inbox = subparsers.add_parser(
        "approval-inbox",
        help="Show app-ready approval cards from Agent Gate receipts.",
    )
    approval_inbox.add_argument("--ledger", required=True, help="Read run ledger JSONL evidence.")
    approval_inbox.add_argument("--json", action="store_true", help="Print approval cards as JSON.")
    approval_inbox.set_defaults(func=cmd_approval_inbox)

    approval_decision = subparsers.add_parser(
        "approval-decision",
        help="Append a local human approval or block decision for an Agent Gate receipt.",
    )
    approval_decision.add_argument("--ledger", required=True, help="Append the decision to this run ledger JSONL file.")
    approval_decision.add_argument("--action-id", required=True, help="Agent Gate action_id to approve or block.")
    approval_decision.add_argument("--decision", required=True, choices=APPROVAL_DECISIONS, help="Human decision to record.")
    approval_decision.add_argument("--approver", required=True, help="Human approver name or handle.")
    approval_decision.add_argument("--reason", help="Optional short reason for the decision.")
    approval_decision.add_argument("--json", action="store_true", help="Print the approval decision receipt as JSON.")
    approval_decision.set_defaults(func=cmd_approval_decision)

    evidence_ingest = subparsers.add_parser(
        "evidence-ingest",
        help="Append recorded evidence from any compatible proof tool for an Agent Gate receipt.",
    )
    evidence_ingest.add_argument("--ledger", required=True, help="Append recorded evidence to this run ledger JSONL file.")
    evidence_ingest.add_argument("--tool", help="Evidence tool id, such as runprint, browser-session, crm-audit, or test-reporter.")
    evidence_ingest.add_argument("--tool-kind", help="Evidence tool kind, such as recorder, monitor, test, browser, crm, or api.")
    evidence_ingest.add_argument("--action-id", help="Agent Gate action_id this evidence proves.")
    evidence_ingest.add_argument("--recording-id", help="Evidence recording id.")
    evidence_ingest.add_argument("--bundle-id", help="Evidence bundle id.")
    evidence_ingest.add_argument(
        "--artifact",
        action="append",
        help="Recorded artifact. Use PATH or id:kind:path. Repeatable.",
    )
    evidence_ingest.add_argument("--summary", help="Short summary of what the evidence tool recorded.")
    evidence_ingest.add_argument("--source", help="Path, URL, or note identifying the evidence source.")
    evidence_ingest.add_argument("--bundle", help="Optional evidence JSON bundle file with action/tool/recording/artifact fields.")
    evidence_ingest.add_argument("--json", action="store_true", help="Print the evidence ingest receipt as JSON.")
    evidence_ingest.set_defaults(func=cmd_evidence_ingest)

    runprint_ingest = subparsers.add_parser(
        "runprint-ingest",
        help="Append external RunPrint recording evidence for an Agent Gate receipt.",
    )
    runprint_ingest.add_argument("--ledger", required=True, help="Append RunPrint evidence to this run ledger JSONL file.")
    runprint_ingest.add_argument("--action-id", help="Agent Gate action_id this recording proves.")
    runprint_ingest.add_argument("--recording-id", help="RunPrint recording id.")
    runprint_ingest.add_argument("--bundle-id", help="RunPrint evidence bundle id.")
    runprint_ingest.add_argument(
        "--artifact",
        action="append",
        help="Recorded artifact. Use PATH or id:kind:path. Repeatable.",
    )
    runprint_ingest.add_argument("--summary", help="Short summary of what RunPrint recorded.")
    runprint_ingest.add_argument("--source", help="Path, URL, or note identifying the RunPrint evidence source.")
    runprint_ingest.add_argument("--bundle", help="Optional RunPrint JSON bundle file with action/recording/artifact fields.")
    runprint_ingest.add_argument("--json", action="store_true", help="Print the RunPrint ingest receipt as JSON.")
    runprint_ingest.set_defaults(func=cmd_runprint_ingest)

    mission_status = subparsers.add_parser(
        "mission-status",
        help="Explain one ledger as plan, gate, approval, proof, and next action.",
    )
    mission_status.add_argument("--ledger", required=True, help="Read run ledger JSONL evidence.")
    mission_status.add_argument("--json", action="store_true", help="Print mission status as JSON.")
    mission_status.set_defaults(func=cmd_mission_status)

    agent_packet = subparsers.add_parser(
        "agent-packet",
        help="Export a BYOA handoff packet from an Agent Gate receipt.",
    )
    agent_packet.add_argument("--ledger", required=True, help="Read run ledger JSONL evidence.")
    agent_packet.add_argument("--action-id", required=True, help="Agent Gate action_id to export.")
    agent_packet.add_argument("--output", help="Write the packet JSON to this path.")
    agent_packet.add_argument("--json", action="store_true", help="Print packet JSON.")
    agent_packet.set_defaults(func=cmd_agent_packet)

    agent_result_ingest = subparsers.add_parser(
        "agent-result-ingest",
        help="Validate and record a custom agent result against an Agent Packet.",
    )
    agent_result_ingest.add_argument("--ledger", required=True, help="Append result evidence to this run ledger JSONL file.")
    agent_result_ingest.add_argument("--action-id", help="Agent Gate action_id this result answers.")
    agent_result_ingest.add_argument("--result", required=True, help="Agent result JSON file returned by the worker agent.")
    agent_result_ingest.add_argument("--json", action="store_true", help="Print the ingest report as JSON.")
    agent_result_ingest.set_defaults(func=cmd_agent_result_ingest)

    validate = subparsers.add_parser("validate", help="Validate a Harnessfile.")
    validate.add_argument("harnessfile")
    validate.set_defaults(func=cmd_validate)

    plan = subparsers.add_parser("plan", help="Compile a Harnessfile into a dry-run plan.")
    plan.add_argument("harnessfile")
    plan.add_argument("--json", action="store_true", help="Print the plan as JSON.")
    plan.add_argument("--ledger", help="Write a dry-run run ledger as JSONL.")
    plan.set_defaults(func=cmd_plan)

    suggest = subparsers.add_parser("suggest", help="Draft a Harnessfile from a plain-language goal.")
    suggest.add_argument("goal", help="Plain-language mission goal.")
    suggest.add_argument("--output", help="Write the suggested Harnessfile to this path.")
    suggest.add_argument("--repository", default="AmmarAlBalkhi/delegation-bot", help="Repository owner/name to place in executor inputs.")
    suggest.add_argument("--owner", default="AmmarAlBalkhi", help="Accountable owner/reviewer login for the suggested mission.")
    suggest.add_argument(
        "--template",
        choices=SUGGESTION_TEMPLATE_IDS,
        help="Force a suggestion template instead of inferring one from the goal.",
    )
    suggest.add_argument(
        "--draft-source",
        choices=("template", "fixture", "model"),
        default="template",
        help="Use the built-in template path, a no-network model fixture, or an opt-in live model call.",
    )
    suggest.add_argument(
        "--provider",
        choices=PROVIDER_CHOICES,
        help="Provider to use when --draft-source fixture or --draft-source model is used.",
    )
    suggest.add_argument(
        "--allow-live-model",
        action="store_true",
        help="Confirm that --draft-source model may call a provider API or local model server.",
    )
    suggest.add_argument("--model", help="Override the default live model for --draft-source model.")
    suggest.add_argument(
        "--base-url",
        help="Override the local model server URL for --draft-source model --provider ollama.",
    )
    suggest.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Live model request timeout in seconds.",
    )
    suggest.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
        help="Maximum live model output tokens.",
    )
    suggest.add_argument("--plan", action="store_true", help="Also compile and print the dry-run plan.")
    suggest.add_argument("--ledger", help="Write a dry-run ledger; requires --plan.")
    suggest.add_argument("--json", action="store_true", help="Print the suggested Harnessfile as JSON.")
    suggest.add_argument("--yaml", action="store_true", help="Print only the suggested Harnessfile YAML when --output is omitted.")
    suggest.set_defaults(func=cmd_suggest)

    adapters = subparsers.add_parser("adapters", help="List built-in adapter contracts.")
    adapters.add_argument("adapter_id", nargs="?", help="Optional adapter id to inspect.")
    adapters.add_argument("--json", action="store_true", help="Print adapter contracts as JSON.")
    adapters.set_defaults(func=cmd_adapters)

    ledger = subparsers.add_parser("ledger", help="Inspect a JSONL run ledger.")
    ledger.add_argument("ledger", help="Path to a run ledger JSONL file.")
    ledger.add_argument("--json", action="store_true", help="Print the ledger view as JSON.")
    ledger.add_argument("--type", dest="event_type", help="Only show recent events with this event type.")
    ledger.add_argument("--status", help="Only show recent events with this status.")
    ledger.add_argument("--action", help="Only show recent events for this action id.")
    ledger.add_argument("--adapter", help="Only show recent events for this adapter id.")
    ledger.add_argument("--limit", type=int, default=12, help="Number of recent matching events to show; 0 shows all.")
    ledger.set_defaults(func=cmd_ledger)

    evidence = subparsers.add_parser(
        "evidence",
        help="Summarize planned recorder evidence bundles from a run ledger.",
    )
    evidence.add_argument("--ledger", required=True, help="Path to a run ledger JSONL file.")
    evidence.add_argument("--json", action="store_true", help="Print the evidence report as JSON.")
    evidence.set_defaults(func=cmd_evidence)

    explain_policy = subparsers.add_parser(
        "explain-policy",
        help="Explain local.classifier policy evidence from a run ledger.",
    )
    explain_policy.add_argument("--ledger", required=True, help="Path to a run ledger JSONL file.")
    explain_policy.add_argument(
        "--draft-source",
        choices=("deterministic", "model"),
        default="deterministic",
        help="Use built-in explanations or an opt-in local model explanation.",
    )
    explain_policy.add_argument(
        "--provider",
        choices=("ollama",),
        default="ollama",
        help="Local model provider for --draft-source model.",
    )
    explain_policy.add_argument(
        "--allow-live-model",
        action="store_true",
        help="Confirm that --draft-source model may call the local Ollama server.",
    )
    explain_policy.add_argument("--model", help="Override the default local model.")
    explain_policy.add_argument("--base-url", help="Override the local Ollama server URL.")
    explain_policy.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Local model request timeout in seconds.",
    )
    explain_policy.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
        help="Maximum local model output tokens.",
    )
    explain_policy.add_argument("--json", action="store_true", help="Print explanations as JSON.")
    explain_policy.set_defaults(func=cmd_explain_policy)

    dashboard = subparsers.add_parser("dashboard", help="Build a read-only dashboard snapshot from a run ledger.")
    dashboard.add_argument("ledger", help="Path to a run ledger JSONL file.")
    dashboard.add_argument("--harnessfile", help="Optional Harnessfile for agents, owners, and repository context.")
    dashboard.add_argument("--json", action="store_true", help="Print the dashboard snapshot as JSON.")
    dashboard.set_defaults(func=cmd_dashboard)

    otel = subparsers.add_parser("otel", help="Export a JSONL run ledger to local OpenTelemetry-style JSON.")
    otel.add_argument("ledger", help="Path to a run ledger JSONL file.")
    otel.add_argument("--output", help="Write the telemetry export JSON to this path.")
    otel.add_argument("--environment", default="local", help="deployment.environment resource value.")
    otel.add_argument("--json", action="store_true", help="Print the full telemetry export as JSON.")
    otel.set_defaults(func=cmd_otel)

    catalog = subparsers.add_parser("catalog", help="Validate and summarize the playbook catalog.")
    catalog.add_argument(
        "catalog",
        nargs="?",
        default="playbooks/catalog.yaml",
        help="Path to the playbook catalog.",
    )
    catalog.add_argument("--json", action="store_true", help="Print the catalog as JSON.")
    catalog.add_argument("--tag", action="append", help="Only show playbooks with this tag. Repeatable.")
    catalog.add_argument("--adapter", action="append", help="Only show playbooks requiring this adapter. Repeatable.")
    catalog.add_argument("--list-tags", action="store_true", help="List known catalog tags.")
    catalog.add_argument("--list-adapters", action="store_true", help="List known catalog adapters.")
    catalog.set_defaults(func=cmd_catalog)

    doctor = subparsers.add_parser("doctor", help="Check local DelegationHQ readiness.")
    doctor.add_argument("--json", action="store_true", help="Print doctor results as JSON.")
    doctor.add_argument(
        "--skip-github",
        action="store_true",
        help="Skip GitHub CLI/auth checks for deterministic local or CI runs.",
    )
    doctor.add_argument(
        "--github-app",
        action="store_true",
        help="Include local GitHub App auth diagnostics without minting a token.",
    )
    doctor.set_defaults(func=cmd_doctor)

    release_check = subparsers.add_parser(
        "release-check",
        help="Check local alpha release readiness without publishing anything.",
    )
    release_check.add_argument(
        "--strict-artifacts",
        action="store_true",
        help="Fail when standalone artifacts such as dist/delegation.exe or checksums are missing.",
    )
    release_check.add_argument("--json", action="store_true", help="Print release readiness as JSON.")
    release_check.set_defaults(func=cmd_release_check)

    github_app_plan = subparsers.add_parser(
        "github-app-plan",
        help="Plan GitHub App permissions and installation-token shape without live auth.",
    )
    github_app_plan.add_argument(
        "--mode",
        choices=MODE_CHOICES,
        default="read-only",
        help="Permission mode to plan.",
    )
    github_app_plan.add_argument("--repository", help="Optional owner/name repository to scope the token request.")
    github_app_plan.add_argument("--output", help="Write the permission plan JSON to this path.")
    github_app_plan.add_argument("--json", action="store_true", help="Print the permission plan as JSON.")
    github_app_plan.set_defaults(func=cmd_github_app_plan)

    artifacts = subparsers.add_parser(
        "artifacts",
        help="Write or verify release artifact checksums and manifest files.",
    )
    artifacts.add_argument("--dist", default="dist", help="Directory containing built release artifacts.")
    artifacts.add_argument(
        "--check",
        action="store_true",
        help="Verify existing checksum and manifest files instead of writing them.",
    )
    artifacts.add_argument("--json", action="store_true", help="Print artifact output as JSON.")
    artifacts.set_defaults(func=cmd_artifacts)

    release_rehearse = subparsers.add_parser(
        "release-rehearse",
        help="Write a local release rehearsal evidence bundle without publishing.",
    )
    release_rehearse.add_argument(
        "--output",
        default=".delegation/release-rehearsal",
        help="Directory to write the local evidence bundle.",
    )
    release_rehearse.add_argument("--dist", default="dist", help="Directory containing built release artifacts.")
    release_rehearse.add_argument(
        "--strict-artifacts",
        action="store_true",
        help="Fail the rehearsal when standalone release artifacts or checksums are missing.",
    )
    release_rehearse.add_argument("--json", action="store_true", help="Print release rehearsal summary as JSON.")
    release_rehearse.set_defaults(func=cmd_release_rehearse)

    apply_issues = subparsers.add_parser(
        "apply-issues",
        help="Preview or live-apply gated GitHub Issue actions from a dry-run ledger.",
    )
    apply_issues.add_argument("harnessfile")
    apply_issues.add_argument("--ledger", required=True, help="Read and append run ledger JSONL evidence.")
    apply_issues.add_argument("--apply", action="store_true", help="Perform live GitHub Issue writes.")
    apply_issues.add_argument(
        "--confirm",
        help="Required confirmation token for live apply: LIVE_GITHUB_ISSUES.",
    )
    apply_issues.add_argument(
        "--auth",
        choices=AUTH_CHOICES,
        default=AUTH_AUTO,
        help="Live GitHub auth source: auto, env-token, or github-app.",
    )
    apply_issues.add_argument("--json", action="store_true", help="Print the apply gate report as JSON.")
    apply_issues.set_defaults(func=cmd_apply_issues)

    apply_actions = subparsers.add_parser(
        "apply-actions",
        help="Preview or live-dispatch gated GitHub Actions workflows from a dry-run ledger.",
    )
    apply_actions.add_argument("harnessfile")
    apply_actions.add_argument("--ledger", required=True, help="Read run ledger JSONL evidence.")
    apply_actions.add_argument(
        "--apply",
        action="store_true",
        help="Perform live GitHub Actions workflow dispatch after all gates pass.",
    )
    apply_actions.add_argument(
        "--confirm",
        help="Required confirmation token for live dispatch: LIVE_GITHUB_ACTIONS.",
    )
    apply_actions.add_argument("--json", action="store_true", help="Print the apply gate report as JSON.")
    apply_actions.set_defaults(func=cmd_apply_actions)

    cancel_actions = subparsers.add_parser(
        "cancel-actions",
        help="Preview or live-cancel a GitHub Actions workflow run.",
    )
    cancel_actions.add_argument("repository", help="Repository in owner/name form.")
    cancel_actions.add_argument("run_id", help="Numeric GitHub Actions workflow run id.")
    cancel_actions.add_argument(
        "--apply",
        action="store_true",
        help="Perform live GitHub Actions workflow cancellation after all gates pass.",
    )
    cancel_actions.add_argument(
        "--confirm",
        help="Required confirmation token: CANCEL_GITHUB_ACTIONS, or FORCE_CANCEL_GITHUB_ACTIONS with --force.",
    )
    cancel_actions.add_argument(
        "--force",
        action="store_true",
        help="Use GitHub's force-cancel endpoint when normal cancellation is not enough.",
    )
    cancel_actions.add_argument("--ledger", help="Append cancellation evidence to this JSONL ledger.")
    cancel_actions.add_argument("--json", action="store_true", help="Print the cancel gate report as JSON.")
    cancel_actions.set_defaults(func=cmd_cancel_actions)

    mcp_gate = subparsers.add_parser(
        "mcp-gate",
        help="Check MCP tool allowlists and risk evidence from a dry-run ledger.",
    )
    mcp_gate.add_argument("harnessfile")
    mcp_gate.add_argument("--ledger", required=True, help="Read run ledger JSONL evidence.")
    mcp_gate.add_argument("--json", action="store_true", help="Print the MCP policy report as JSON.")
    mcp_gate.set_defaults(func=cmd_mcp_gate)

    eval_parser = subparsers.add_parser("eval", help="Run built-in evals against a ledger.")
    eval_parser.add_argument("harnessfile")
    eval_parser.add_argument("--ledger", required=True, help="Read run ledger JSONL evidence.")
    eval_parser.add_argument("--json", action="store_true", help="Print eval report as JSON.")
    eval_parser.add_argument("--write", action="store_true", help="Append eval result events to the ledger.")
    eval_parser.add_argument(
        "--feedback",
        action="store_true",
        help="Also draft feedback issues directly from the eval results.",
    )
    eval_parser.add_argument("--feedback-repository", help="Target repository for planned feedback issues.")
    eval_parser.add_argument(
        "--feedback-include-blocked",
        action="store_true",
        help="Also draft issues for blocked eval results.",
    )
    eval_parser.add_argument(
        "--feedback-blocked-repeat-threshold",
        type=int,
        default=1,
        help="Minimum matching blocked eval occurrences before direct feedback drafts.",
    )
    eval_parser.add_argument(
        "--feedback-write",
        action="store_true",
        help="Append planned feedback issue events to the ledger.",
    )
    eval_parser.set_defaults(func=cmd_eval)

    feedback = subparsers.add_parser("feedback", help="Draft dry-run GitHub Issues from failed eval results.")
    feedback.add_argument("harnessfile")
    feedback.add_argument("--ledger", required=True, help="Read run ledger JSONL eval evidence.")
    feedback.add_argument("--repository", help="Target repository for planned feedback issues.")
    feedback.add_argument("--include-blocked", action="store_true", help="Also draft issues for blocked eval results.")
    feedback.add_argument(
        "--blocked-repeat-threshold",
        type=int,
        default=2,
        help="Minimum matching blocked eval occurrences before drafting an issue; use 1 for immediate blocked drafts.",
    )
    feedback.add_argument("--json", action="store_true", help="Print feedback issue drafts as JSON.")
    feedback.add_argument("--write", action="store_true", help="Append planned feedback issue events to the ledger.")
    feedback.set_defaults(func=cmd_feedback)

    recover_feedback = subparsers.add_parser(
        "recover-feedback",
        help="Draft dry-run GitHub Issue updates for feedback issues whose evals now pass.",
    )
    recover_feedback.add_argument("harnessfile")
    recover_feedback.add_argument("--ledger", required=True, help="Read run ledger JSONL eval and feedback evidence.")
    recover_feedback.add_argument("--repository", help="Target repository for planned feedback recovery issues.")
    recover_feedback.add_argument("--json", action="store_true", help="Print feedback recovery drafts as JSON.")
    recover_feedback.add_argument("--write", action="store_true", help="Append planned feedback recovery events.")
    recover_feedback.set_defaults(func=cmd_recover_feedback)

    apply_feedback = subparsers.add_parser(
        "apply-feedback",
        help="Preview or live-apply feedback recovery comments to GitHub Issues.",
    )
    apply_feedback.add_argument("harnessfile")
    apply_feedback.add_argument("--ledger", required=True, help="Read and append feedback recovery ledger evidence.")
    apply_feedback.add_argument("--repository", help="Target repository for planned feedback recovery issues.")
    apply_feedback.add_argument(
        "--apply",
        action="store_true",
        help="Perform live GitHub feedback issue writes after all gates pass.",
    )
    apply_feedback.add_argument(
        "--close",
        action="store_true",
        help="Close the live feedback issue after posting the recovery comment.",
    )
    apply_feedback.add_argument(
        "--confirm",
        help="Required confirmation token: LIVE_FEEDBACK_ISSUES, or CLOSE_FEEDBACK_ISSUES with --close.",
    )
    apply_feedback.add_argument(
        "--auth",
        choices=AUTH_CHOICES,
        default=AUTH_AUTO,
        help="Live GitHub auth source: auto, env-token, or github-app.",
    )
    apply_feedback.add_argument("--json", action="store_true", help="Print the feedback apply gate report as JSON.")
    apply_feedback.set_defaults(func=cmd_apply_feedback)

    promote = subparsers.add_parser("promote", help="Evaluate agent promotion readiness.")
    promote.add_argument("harnessfile")
    promote.add_argument("--ledger", required=True, help="Read run ledger JSONL evidence.")
    promote.add_argument("--json", action="store_true", help="Print promotion report as JSON.")
    promote.set_defaults(func=cmd_promote)

    return parser


def main(argv: T.Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
