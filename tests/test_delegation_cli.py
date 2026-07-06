from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from delegation_bot.cli import main
from delegation_bot.model_suggest_fixtures import ModelSuggestionDraft
from delegation_bot.suggest import build_suggestion


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "ai-harness-control-plane.yaml"


class DelegationCliTests(unittest.TestCase):
    def test_validate_example(self) -> None:
        with redirect_stdout(io.StringIO()):
            status = main(["validate", str(EXAMPLE)])

        self.assertEqual(status, 0)

    def test_plan_example_writes_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                status = main(["plan", str(EXAMPLE), "--ledger", str(ledger)])
            lines = ledger.read_text(encoding="utf-8").splitlines()

        self.assertEqual(status, 0)
        self.assertGreater(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["type"], "plan.compiled")

    def test_demo_command_runs_built_in_mission_control_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "demo.jsonl"
            with redirect_stdout(io.StringIO()) as output:
                status = main(["demo", "--ledger", str(ledger)])
            lines = ledger.read_text(encoding="utf-8").splitlines()

        self.assertEqual(status, 0)
        self.assertIn("DelegationHQ Demo", output.getvalue())
        self.assertIn("Status: ready", output.getvalue())
        self.assertIn("mcp-gate", output.getvalue())
        self.assertIn("actions-preview", output.getvalue())
        self.assertEqual(json.loads(lines[0])["type"], "plan.compiled")

    def test_demo_command_can_print_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "demo.jsonl"
            with redirect_stdout(io.StringIO()) as output:
                status = main(["demo", "--ledger", str(ledger), "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["mcp_gate"]["status"], "ready")
        self.assertTrue(data["ledger_event_count"])

    def test_init_command_writes_starter_harnessfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            harnessfile = Path(tmpdir) / "Harnessfile.yaml"
            ledger = Path(tmpdir) / "init.jsonl"
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "init",
                        "--goal",
                        "review this pull request",
                        "--output",
                        str(harnessfile),
                        "--repository",
                        "owner/example",
                        "--owner",
                        "owner",
                        "--plan",
                        "--ledger",
                        str(ledger),
                    ]
                )
            harness_text = harnessfile.read_text(encoding="utf-8")
            ledger_lines = ledger.read_text(encoding="utf-8").splitlines()

        self.assertEqual(status, 0)
        self.assertIn("Starter Harnessfile Created", output.getvalue())
        self.assertIn("Template: code-review", output.getvalue())
        self.assertIn("owner/example", harness_text)
        self.assertEqual(json.loads(ledger_lines[0])["type"], "plan.compiled")

    def test_init_command_does_not_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            harnessfile = Path(tmpdir) / "Harnessfile.yaml"
            harnessfile.write_text("existing", encoding="utf-8")
            with redirect_stderr(io.StringIO()) as error:
                status = main(["init", "--output", str(harnessfile)])

        self.assertEqual(status, 1)
        self.assertIn("--force", error.getvalue())

    def test_suggest_writes_valid_harnessfile_and_plan_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            harnessfile = Path(tmpdir) / "suggested.yaml"
            ledger = Path(tmpdir) / "suggested.jsonl"
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "suggest",
                        "prepare this repo for release",
                        "--output",
                        str(harnessfile),
                        "--plan",
                        "--ledger",
                        str(ledger),
                    ]
            )
            harnessfile_exists = harnessfile.exists()
            ledger_lines = ledger.read_text(encoding="utf-8").splitlines()

        self.assertEqual(status, 0)
        self.assertIn("Suggested Harnessfile", output.getvalue())
        self.assertIn("Template: release-readiness", output.getvalue())
        self.assertTrue(harnessfile_exists)
        self.assertEqual(json.loads(ledger_lines[0])["type"], "plan.compiled")

    def test_suggest_default_output_stays_short(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(["suggest", "refresh the README docs"])

        self.assertEqual(status, 0)
        self.assertIn("Suggested Harnessfile", output.getvalue())
        self.assertIn("Tip: add `--output", output.getvalue())
        self.assertNotIn("version: delegation.ai/v1", output.getvalue())

    def test_suggest_fixture_writes_valid_model_backed_harnessfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            harnessfile = Path(tmpdir) / "suggested.yaml"
            ledger = Path(tmpdir) / "suggested.jsonl"
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "suggest",
                        "prepare this repo for release",
                        "--draft-source",
                        "fixture",
                        "--provider",
                        "openai",
                        "--output",
                        str(harnessfile),
                        "--plan",
                        "--ledger",
                        str(ledger),
                    ]
                )
            lines = ledger.read_text(encoding="utf-8").splitlines()
            harness_text = harnessfile.read_text(encoding="utf-8")

        self.assertEqual(status, 0)
        self.assertIn("No-network openai model fixture", output.getvalue())
        self.assertIn("model-fixture-openai-release-readiness", harness_text)
        self.assertEqual(json.loads(lines[0])["type"], "plan.compiled")

    def test_suggest_model_requires_explicit_live_gate(self) -> None:
        with redirect_stderr(io.StringIO()) as error:
            status = main(
                [
                    "suggest",
                    "prepare this repo for release",
                    "--draft-source",
                    "model",
                    "--provider",
                    "openai",
                ]
            )

        self.assertEqual(status, 1)
        self.assertIn("--allow-live-model", error.getvalue())

    def test_suggest_model_can_use_mocked_live_provider(self) -> None:
        suggestion = build_suggestion("prepare this repo for release")
        manifest = dict(suggestion.manifest)
        manifest["metadata"] = {**manifest["metadata"], "suggested_by": "delegation.suggest.model"}
        draft = ModelSuggestionDraft(
            goal="prepare this repo for release",
            provider="openai",
            model="gpt-test",
            rationale="Mocked live model draft.",
            manifest=manifest,
            safety_notes=("Dry-run first.",),
            validation_expectations=("Harnessfile validates.",),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            harnessfile = Path(tmpdir) / "live.yaml"
            ledger = Path(tmpdir) / "live.jsonl"
            with patch("delegation_bot.cli.build_live_model_config") as config_mock, patch(
                "delegation_bot.cli.fetch_live_model_suggestion", return_value=draft
            ) as fetch_mock, redirect_stdout(io.StringIO()) as output:
                config_mock.return_value = object()
                status = main(
                    [
                        "suggest",
                        "prepare this repo for release",
                        "--draft-source",
                        "model",
                        "--provider",
                        "openai",
                        "--allow-live-model",
                        "--model",
                        "gpt-test",
                        "--output",
                        str(harnessfile),
                        "--plan",
                        "--ledger",
                        str(ledger),
                    ]
                )
            ledger_lines = ledger.read_text(encoding="utf-8").splitlines()

        self.assertEqual(status, 0)
        self.assertIn("Live openai model draft", output.getvalue())
        self.assertEqual(json.loads(ledger_lines[0])["type"], "plan.compiled")
        self.assertTrue(fetch_mock.called)

    def test_suggest_model_can_use_mocked_ollama_provider(self) -> None:
        suggestion = build_suggestion("prepare this repo for release")
        manifest = dict(suggestion.manifest)
        manifest["metadata"] = {**manifest["metadata"], "suggested_by": "delegation.suggest.model"}
        draft = ModelSuggestionDraft(
            goal="prepare this repo for release",
            provider="ollama",
            model="llama-test",
            rationale="Mocked local model draft.",
            manifest=manifest,
            safety_notes=("Dry-run first.",),
            validation_expectations=("Harnessfile validates.",),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            harnessfile = Path(tmpdir) / "local.yaml"
            ledger = Path(tmpdir) / "local.jsonl"
            with patch("delegation_bot.cli.build_live_model_config") as config_mock, patch(
                "delegation_bot.cli.fetch_live_model_suggestion", return_value=draft
            ) as fetch_mock, redirect_stdout(io.StringIO()) as output:
                config_mock.return_value = object()
                status = main(
                    [
                        "suggest",
                        "prepare this repo for release",
                        "--draft-source",
                        "model",
                        "--provider",
                        "ollama",
                        "--allow-live-model",
                        "--model",
                        "llama-test",
                        "--base-url",
                        "http://127.0.0.1:11434",
                        "--output",
                        str(harnessfile),
                        "--plan",
                        "--ledger",
                        str(ledger),
                    ]
                )
            ledger_lines = ledger.read_text(encoding="utf-8").splitlines()

        self.assertEqual(status, 0)
        self.assertIn("Live ollama model draft", output.getvalue())
        self.assertEqual(json.loads(ledger_lines[0])["type"], "plan.compiled")
        self.assertTrue(fetch_mock.called)

    def test_fixture_mode_rejects_ollama_without_network(self) -> None:
        with redirect_stderr(io.StringIO()) as error:
            status = main(["suggest", "prepare this repo for release", "--draft-source", "fixture", "--provider", "ollama"])

        self.assertEqual(status, 1)
        self.assertIn("no-network fixtures", error.getvalue())

    def test_promote_example_reads_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            ledger.write_text(
                json.dumps(
                    {
                        "type": "eval.result",
                        "status": "passed",
                        "details": {"eval_id": "tests_pass_before_pr"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with redirect_stdout(io.StringIO()) as output:
                status = main(["promote", str(EXAMPLE), "--ledger", str(ledger)])

        self.assertEqual(status, 0)
        self.assertIn("Promotion report", output.getvalue())

    def test_eval_example_appends_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
                status = main(["eval", str(EXAMPLE), "--ledger", str(ledger), "--write"])
            lines = ledger.read_text(encoding="utf-8").splitlines()

        self.assertEqual(status, 0)
        self.assertTrue(any(json.loads(line)["type"] == "eval.result" for line in lines))

    def test_eval_can_draft_feedback_directly_without_written_eval_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "eval",
                        str(EXAMPLE),
                        "--ledger",
                        str(ledger),
                        "--feedback",
                        "--feedback-include-blocked",
                    ]
                )
            lines = ledger.read_text(encoding="utf-8").splitlines()

        self.assertEqual(status, 0)
        self.assertIn("Eval report", output.getvalue())
        self.assertIn("Feedback issue drafts", output.getvalue())
        self.assertIn("Eval blocked: tests_pass_before_pr", output.getvalue())
        self.assertFalse(any(json.loads(line)["type"] == "eval.result" for line in lines))

    def test_eval_feedback_write_appends_planned_issue_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
                status = main(
                    [
                        "eval",
                        str(EXAMPLE),
                        "--ledger",
                        str(ledger),
                        "--feedback",
                        "--feedback-include-blocked",
                        "--feedback-write",
                    ]
                )
            lines = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(status, 0)
        self.assertTrue(any(line["type"] == "github.issue.planned" for line in lines))
        self.assertFalse(any(line["type"] == "eval.result" for line in lines))

    def test_eval_feedback_write_requires_feedback_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stderr(io.StringIO()):
                status = main(["eval", str(EXAMPLE), "--ledger", str(ledger), "--feedback-write"])

        self.assertEqual(status, 1)

    def test_feedback_example_drafts_issue_from_blocked_eval(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
                self.assertEqual(main(["eval", str(EXAMPLE), "--ledger", str(ledger), "--write"]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "feedback",
                        str(EXAMPLE),
                        "--ledger",
                        str(ledger),
                        "--include-blocked",
                        "--blocked-repeat-threshold",
                        "1",
                    ]
                )

        self.assertEqual(status, 0)
        self.assertIn("Feedback issue drafts", output.getvalue())
        self.assertIn("Eval blocked: tests_pass_before_pr", output.getvalue())

    def test_recover_feedback_drafts_resolution_update(self) -> None:
        source = ROOT / "examples" / "ledgers" / "feedback-recovery.jsonl"
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "feedback-recovery.jsonl"
            harnessfile = Path(tmpdir) / "feedback-harness.json"
            ledger.write_text("\n".join(source.read_text(encoding="utf-8").splitlines()[:-1]) + "\n", encoding="utf-8")
            harnessfile.write_text(
                json.dumps(
                    {
                        "version": "delegation.ai/v1",
                        "id": "feedback-memory-fixture",
                        "objective": "Show feedback recovery.",
                        "triggers": [{"type": "manual"}],
                        "executors": [{"id": "feedback_issue", "kind": "workflow", "adapter": "github.issue"}],
                        "outputs": ["github.issue"],
                        "policies": {"permissions": {"allowed_repositories": ["AmmarAlBalkhi/delegation-bot"]}},
                    }
                ),
                encoding="utf-8",
            )
            with redirect_stdout(io.StringIO()) as output:
                status = main(["recover-feedback", str(harnessfile), "--ledger", str(ledger)])

        self.assertEqual(status, 0)
        self.assertIn("Feedback issue drafts", output.getvalue())
        self.assertIn("Resolve eval passed: required_adapter_evidence", output.getvalue())
        self.assertIn("operation: resolve", output.getvalue())

    def test_dashboard_command_builds_read_only_snapshot(self) -> None:
        ledger = ROOT / "examples" / "ledgers" / "feedback-recovery.jsonl"

        with redirect_stdout(io.StringIO()) as output:
            status = main(["dashboard", str(ledger), "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["counts"]["feedback_items"], 1)
        self.assertEqual(data["feedback"][0]["operation"], "resolve")

    def test_ledger_command_summarizes_adapter_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["ledger", str(ledger), "--adapter", "github.issue"])

        self.assertEqual(status, 0)
        self.assertIn("Ledger report", output.getvalue())
        self.assertIn("github.issue", output.getvalue())
        self.assertIn("issue_marker", output.getvalue())

    def test_ledger_command_can_print_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["ledger", str(ledger), "--json", "--limit", "2"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["source"], str(ledger))
        self.assertTrue(data["adapter_evidence"])
        self.assertEqual(data["shown_event_count"], 2)

    def test_explain_policy_command_summarizes_classifier_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["explain-policy", "--ledger", str(ledger)])

        self.assertEqual(status, 0)
        self.assertIn("Policy Explanation", output.getvalue())
        self.assertIn("Deterministic gates still decide", output.getvalue())

    def test_otel_command_exports_trace_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            otel = Path(tmpdir) / "otel.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["otel", str(ledger), "--output", str(otel)])
            data = json.loads(otel.read_text(encoding="utf-8"))

        self.assertEqual(status, 0)
        self.assertIn("OpenTelemetry export", output.getvalue())
        self.assertEqual(data["format"], "delegation.otel.trace.v1")
        self.assertTrue(data["traces"][0]["spans"])

    def test_adapters_command_lists_contracts(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(["adapters"])

        self.assertEqual(status, 0)
        self.assertIn("anthropic.messages", output.getvalue())
        self.assertIn("claude.code", output.getvalue())
        self.assertIn("codex.thread", output.getvalue())
        self.assertIn("mcp.tool", output.getvalue())
        self.assertIn("sample.echo", output.getvalue())

    def test_adapters_command_can_print_one_contract_as_json(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(["adapters", "codex.thread", "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data[0]["id"], "codex.thread")
        self.assertIn("qa_result", data[0]["required_evidence"])

    def test_catalog_command_summarizes_playbooks(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(["catalog"])

        self.assertEqual(status, 0)
        self.assertIn("Playbook catalog", output.getvalue())
        self.assertIn("playbook-code-review", output.getvalue())

    def test_catalog_command_can_print_json(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(["catalog", "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["version"], "delegation.ai/playbook-catalog/v1")
        self.assertGreaterEqual(len(data["playbooks"]), 3)

    def test_catalog_command_filters_by_tag_and_adapter(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(["catalog", "--tag", "release", "--adapter", "github.actions"])

        self.assertEqual(status, 0)
        self.assertIn("Filters: tags=release; adapters=github.actions", output.getvalue())
        self.assertIn("playbook-release-readiness", output.getvalue())
        self.assertNotIn("playbook-code-review", output.getvalue())

    def test_catalog_command_json_includes_filter_metadata(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(["catalog", "--tag", "ci", "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["filters"]["tags"], ["ci"])
        self.assertEqual(data["filtered_count"], 1)
        self.assertEqual(data["playbooks"][0]["id"], "playbook-ci-repair")

    def test_catalog_command_lists_tags_and_adapters(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(["catalog", "--list-tags", "--list-adapters"])

        self.assertEqual(status, 0)
        self.assertIn("Catalog tags", output.getvalue())
        self.assertIn("release", output.getvalue())
        self.assertIn("Catalog adapters", output.getvalue())
        self.assertIn("github.issue", output.getvalue())

    def test_doctor_command_reports_readiness(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(["doctor", "--skip-github"])

        self.assertEqual(status, 0)
        self.assertIn("Delegation Doctor", output.getvalue())
        self.assertIn("Suggest Loop", output.getvalue())

    def test_doctor_command_can_print_json(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(["doctor", "--skip-github", "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["failed_count"], 0)
        self.assertTrue(any(check["id"] == "suggest_loop" for check in data["checks"]))

    def test_apply_issues_previews_gated_github_issue_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["apply-issues", str(EXAMPLE), "--ledger", str(ledger)])

        self.assertEqual(status, 0)
        self.assertIn("GitHub Issue Apply Gate", output.getvalue())
        self.assertIn("Status: ready", output.getvalue())
        self.assertIn("Rerun with `--apply --confirm LIVE_GITHUB_ISSUES`", output.getvalue())

    def test_apply_issues_live_mode_blocks_without_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "apply-issues",
                        str(EXAMPLE),
                        "--ledger",
                        str(ledger),
                        "--apply",
                        "--confirm",
                        "LIVE_GITHUB_ISSUES",
                    ]
                )

        self.assertEqual(status, 1)
        self.assertIn("GITHUB_TOKEN or GH_TOKEN is required", output.getvalue())

    def test_apply_actions_previews_gated_workflow_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["apply-actions", str(EXAMPLE), "--ledger", str(ledger)])

        self.assertEqual(status, 0)
        self.assertIn("GitHub Actions Apply Gate", output.getvalue())
        self.assertIn("Status: ready", output.getvalue())
        self.assertIn("actions/runs/dryrun-gha", output.getvalue())

    def test_apply_actions_live_mode_blocks_without_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "apply-actions",
                        str(EXAMPLE),
                        "--ledger",
                        str(ledger),
                        "--apply",
                        "--confirm",
                        "LIVE_GITHUB_ACTIONS",
                    ]
                )

        self.assertEqual(status, 1)
        self.assertIn("GITHUB_TOKEN or GH_TOKEN is required", output.getvalue())

    def test_mcp_gate_reports_ready_policy_for_example(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["mcp-gate", str(EXAMPLE), "--ledger", str(ledger)])

        self.assertEqual(status, 0)
        self.assertIn("MCP Tool Policy Gate", output.getvalue())
        self.assertIn("Status: ready", output.getvalue())
        self.assertIn("local-repository-tools/inspect_repository", output.getvalue())

    def test_mcp_gate_json_contains_tool_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["mcp-gate", str(EXAMPLE), "--ledger", str(ledger), "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["drafts"][0]["tool_ref"], "local-repository-tools/inspect_repository")


if __name__ == "__main__":
    unittest.main()
