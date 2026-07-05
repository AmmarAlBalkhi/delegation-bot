#!/usr/bin/env python3
"""Delegation Bot command line interface."""

from __future__ import annotations

import argparse
import json
import sys
import typing as T
from pathlib import Path

from delegation_bot.adapters import get_adapter_contract, list_adapter_contracts, render_adapter_contracts
from delegation_bot.dashboard import build_dashboard_snapshot, render_dashboard_snapshot
from delegation_bot.doctor import render_doctor_report, run_doctor
from delegation_bot.evals import EvalError, append_jsonl, eval_results_to_events, load_jsonl, render_eval_report, run_declared_evals
from delegation_bot.eval_feedback import (
    append_feedback_events,
    build_feedback_issue_drafts,
    build_feedback_issue_drafts_from_results,
    build_feedback_resolution_drafts,
    feedback_drafts_to_events,
    render_feedback_report,
)
from delegation_bot.github_issue_apply import (
    GitHubIssueClient,
    apply_github_issue_drafts,
    build_apply_report,
    github_token_from_env,
    render_apply_report,
)
from delegation_bot.harness_manifest import ManifestError, load_manifest, summarize_manifest, validate_manifest
from delegation_bot.harness_plan import PlanError, build_dry_run_ledger, compile_plan, render_plan, write_jsonl
from delegation_bot.ledger import LedgerError, LedgerFilter, build_ledger_view, load_ledger_events, render_ledger_view
from delegation_bot.model_suggest_fixtures import (
    ModelSuggestionFixtureError,
    SUPPORTED_PROVIDERS,
    load_model_suggestion_fixture,
)
from delegation_bot.model_suggest_live import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_TIMEOUT_SECONDS,
    LiveModelSuggestionError,
    build_live_model_config,
    fetch_live_model_suggestion,
)
from delegation_bot.otel_export import OtelExportError, build_otel_export, render_otel_export, write_otel_export
from delegation_bot.playbook_catalog import (
    PlaybookCatalogError,
    catalog_facets,
    filter_catalog,
    load_catalog,
    summarize_catalog,
    validate_catalog,
)
from delegation_bot.promotion import PromotionError, evaluate_promotions, load_ledger, render_promotion_report
from delegation_bot.suggest import (
    SUGGESTION_TEMPLATE_IDS,
    HarnessSuggestion,
    build_suggestion,
    infer_template,
    manifest_to_yaml,
    render_suggestion,
)


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


def cmd_suggest(args: argparse.Namespace) -> int:
    try:
        if args.draft_source == "fixture":
            if not args.provider:
                print("ERROR: --provider is required when --draft-source fixture is used", file=sys.stderr)
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
            if not args.allow_live_model:
                print(
                    "ERROR: live model suggestions are opt-in. Add --allow-live-model to confirm "
                    "you want a provider API call and possible cost.",
                    file=sys.stderr,
                )
                return 1
            config = build_live_model_config(
                args.provider,
                model=args.model,
                timeout_seconds=args.timeout_seconds,
                max_output_tokens=args.max_output_tokens,
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
    report = run_doctor(include_github=not args.skip_github)
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

    token = github_token_from_env()
    report = build_apply_report(
        manifest,
        plan,
        ledger_events,
        ledger_source=str(ledger_path),
        apply=args.apply,
        confirmation=args.confirm,
        token=token,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_apply_report(report))

    if report.blocked:
        return 1

    if not args.apply:
        return 0

    run_id = str(ledger_events[0].get("run_id")) if ledger_events else f"apply-{plan.id}"
    events = apply_github_issue_drafts(
        report.drafts,
        client=GitHubIssueClient(token or ""),
        run_id=run_id,
        start_sequence=len(ledger_events) + 1,
    )
    try:
        append_jsonl(events, ledger_path)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not args.json:
        print(f"\nApply events appended: {ledger_path}")
    return 1 if any(event.status == "failed" for event in events) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

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
        choices=SUPPORTED_PROVIDERS,
        help="Provider to use when --draft-source fixture or --draft-source model is used.",
    )
    suggest.add_argument(
        "--allow-live-model",
        action="store_true",
        help="Confirm that --draft-source model may call a provider API and incur cost.",
    )
    suggest.add_argument("--model", help="Override the default live model for --draft-source model.")
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

    doctor = subparsers.add_parser("doctor", help="Check local Delegation Bot readiness.")
    doctor.add_argument("--json", action="store_true", help="Print doctor results as JSON.")
    doctor.add_argument(
        "--skip-github",
        action="store_true",
        help="Skip GitHub CLI/auth checks for deterministic local or CI runs.",
    )
    doctor.set_defaults(func=cmd_doctor)

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
    apply_issues.add_argument("--json", action="store_true", help="Print the apply gate report as JSON.")
    apply_issues.set_defaults(func=cmd_apply_issues)

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
