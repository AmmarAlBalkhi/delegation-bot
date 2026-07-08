from __future__ import annotations

import json
import io
import sys
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
    def test_version_command_prints_package_version(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as raised:
                main(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("DelegationHQ 0.1.0a0", output.getvalue())

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

    def test_demo_control_loop_records_gate_approval_and_runprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "demo.jsonl"
            with redirect_stdout(io.StringIO()) as output:
                status = main(["demo", "--ledger", str(ledger), "--control-loop", "--approver", "Ammar"])
            events = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
            event_types = [event["type"] for event in events]

        self.assertEqual(status, 0)
        self.assertIn("Control loop:", output.getvalue())
        self.assertIn("RunPrint audit: recorded", output.getvalue())
        self.assertIn("agent.gate.previewed", event_types)
        self.assertIn("approval.granted", event_types)
        self.assertIn("runprint.recording.completed", event_types)

    def test_mission_status_command_explains_control_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "demo.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["demo", "--ledger", str(ledger), "--control-loop", "--approver", "Ammar"]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["mission-status", "--ledger", str(ledger), "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["status"], "recorded")
        self.assertEqual(data["control_loop"]["gate_previews"], 1)
        self.assertEqual(data["control_loop"]["runprint_recorded_events"], 1)
        self.assertEqual(data["control_loop"]["pending_approval"], 0)
        self.assertIn("agent_gate.planner.write_issue_draft", data["control_loop"]["primary_action_id"])

    def test_agent_packet_command_exports_byoa_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "demo.jsonl"
            packet_path = Path(tmpdir) / "packet.json"
            action_id = "agent_gate.planner.write_issue_draft"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["demo", "--ledger", str(ledger), "--control-loop", "--approver", "Ammar"]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "agent-packet",
                        "--ledger",
                        str(ledger),
                        "--action-id",
                        action_id,
                        "--output",
                        str(packet_path),
                    ]
                )
            data = json.loads(packet_path.read_text(encoding="utf-8"))

        self.assertEqual(status, 0)
        self.assertIn("Agent Packet", output.getvalue())
        self.assertEqual(data["status"], "recorded")
        self.assertEqual(data["packet"]["agent"]["id"], "planner")
        self.assertEqual(data["packet"]["requested_work"]["action"], "write.issue_draft")
        self.assertTrue(data["packet"]["current_receipts"]["runprint_recorded"])
        self.assertEqual(data["packet"]["return_contract"]["schema_version"], "delegation.agent-result.v1")
        self.assertIn("agent-result-ingest", data["packet"]["return_contract"]["ingest_command"])
        self.assertIn("evidence-ingest", data["packet"]["return_contract"]["evidence_ingest_command"])
        self.assertEqual(data["packet"]["return_contract"]["example"]["evidence_tool"], "evidence-tool")

    def test_app_plan_command_is_human_readable(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(["app-plan"])

        self.assertEqual(status, 0)
        self.assertIn("DelegationHQ EXE App Plan", output.getvalue())
        self.assertIn("Mission Snapshot", output.getvalue())
        self.assertIn("Bring Your Own Agent", output.getvalue())
        self.assertIn("Visual/interface design waits", output.getvalue())

    def test_app_plan_command_can_print_json(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(["app-plan", "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["app_name"], "DelegationHQ Local Mission Cockpit")
        self.assertTrue(any(surface["id"] == "agent_passports" for surface in data["surfaces"]))
        self.assertIn("runtime type", data["bring_your_own_agent"]["passport_fields"])

    def test_app_state_command_is_human_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["app-state", "--ledger", str(ledger), "--harnessfile", str(EXAMPLE)])

        self.assertEqual(status, 0)
        text = output.getvalue()
        self.assertIn("DelegationHQ App State", text)
        self.assertIn("Doctor: ready", text)
        self.assertIn("Ledger: planned", text)
        self.assertIn("evidence bundles: 1", text)
        self.assertIn("This state command is read-only.", text)

    def test_app_state_command_can_print_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["app-state", "--ledger", str(ledger), "--harnessfile", str(EXAMPLE), "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["schema_version"], "delegation.app-state.v1")
        self.assertTrue(data["read_only"])
        self.assertEqual(data["live_risk"], "none")
        self.assertEqual(data["app_plan"]["app_name"], "DelegationHQ Local Mission Cockpit")
        self.assertEqual(data["ledger"]["event_count"], data["ledger"]["dashboard"]["counts"]["events"])
        self.assertEqual(data["ledger"]["evidence"]["bundle_count"], 1)
        self.assertEqual(data["ledger"]["agent_audit"]["status"], "missing_gate")
        self.assertEqual(data["ledger"]["approval_inbox"]["status"], "empty")
        self.assertEqual(data["agents"]["passport_count"], 4)
        self.assertEqual(data["agent_gate"]["status"], "not_requested")
        self.assertIn("delegation app-state --ledger .delegation/demo.jsonl --json", data["next_actions"])

    def test_app_state_can_include_custom_agent_registry(self) -> None:
        registry = ROOT / "examples" / "agent-passports.yaml"
        with redirect_stdout(io.StringIO()) as output:
            status = main(["app-state", "--agent-registry", str(registry), "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["agents"]["passport_count"], 2)
        self.assertTrue(any(passport["id"] == "crm_update_agent" for passport in data["agents"]["passports"]))

    def test_app_state_can_use_workspace_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["workspace-init", "--path", tmpdir, "--plan"]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["app-state", "--workspace", tmpdir, "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["workspace"]["status"], "ready")
        self.assertEqual(data["workspace"]["agent_count"], 1)
        self.assertEqual(data["ledger"]["status"], "planned")
        self.assertGreaterEqual(data["agents"]["passport_count"], 1)
        self.assertIn("delegation app-state --workspace", " ".join(data["next_actions"]))

    def test_cockpit_command_uses_workspace_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["workspace-init", "--path", tmpdir, "--plan"]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["cockpit", "--workspace", tmpdir])

        self.assertEqual(status, 0)
        text = output.getvalue()
        self.assertIn("DelegationHQ App State", text)
        self.assertIn("Workspace:", text)
        self.assertIn("GitHub required: false", text)

    def test_approval_preview_uses_workspace_agent_passport(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["workspace-init", "--path", tmpdir, "--plan"]), 0)
                self.assertEqual(
                    main(
                        [
                            "agent-add",
                            "preview_runner",
                            "--workspace",
                            tmpdir,
                            "--command",
                            f"{sys.executable} -c \"print('preview ok')\"",
                            "--capability",
                            "read.workspace",
                            "--allowed-data",
                            "workspace",
                            "--evidence",
                            "command_output",
                            "--force",
                        ]
                    ),
                    0,
                )
            with redirect_stdout(io.StringIO()) as output:
                status = main(["approval-preview", "preview_runner", "--workspace", tmpdir, "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["schema_version"], "delegation.approval-preview.v1")
        self.assertEqual(data["decision"], "allow")
        self.assertEqual(data["agent_id"], "preview_runner")
        self.assertTrue(data["can_execute"])
        self.assertIn("command_output", data["required_evidence"])
        self.assertEqual(data["request_context"]["intent"], "preview_runner wants to read workspace")
        self.assertEqual(data["resource_summary"]["target_kind"], "workspace")
        self.assertEqual(data["evidence_status"]["status"], "missing")
        self.assertEqual(data["action_intent"]["execution_mode"], "local_command")
        self.assertEqual(data["action_intent"]["workspace_effect"], "read_only")
        self.assertEqual(data["action_intent"]["live_effect"], "read_only_allowed")
        self.assertEqual(data["action_intent"]["confirmation"], "exact_execution_token")
        self.assertIn("command_output", data["action_intent"]["evidence_to_collect"])
        self.assertEqual(data["history"]["status"], "no_history")

    def test_approval_preview_includes_history_note_and_expiration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["workspace-init", "--path", tmpdir, "--plan"]), 0)
                self.assertEqual(
                    main(
                        [
                            "agent-add",
                            "history_runner",
                            "--workspace",
                            tmpdir,
                            "--command",
                            f"{sys.executable} -c \"print('history ok')\"",
                            "--capability",
                            "read.workspace",
                            "--allowed-data",
                            "workspace",
                            "--evidence",
                            "command_output",
                            "--force",
                        ]
                    ),
                    0,
                )
                for _ in range(2):
                    self.assertEqual(
                        main(
                            [
                                "agent-run",
                                "history_runner",
                                "--workspace",
                                tmpdir,
                                "--execute",
                                "--confirm",
                                "LOCAL_AGENT_EXECUTION",
                            ]
                        ),
                        0,
                    )
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "approval-preview",
                        "history_runner",
                        "--workspace",
                        tmpdir,
                        "--review-note",
                        "tests passed locally",
                        "--expires-at",
                        "2099-01-01T00:00:00Z",
                        "--json",
                    ]
                )
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["reviewer_note"], "tests passed locally")
        self.assertEqual(data["expires_at"], "2099-01-01T00:00:00Z")
        self.assertFalse(data["expired"])
        self.assertEqual(data["history"]["status"], "has_history")
        self.assertEqual(data["history"]["gate_count"], 2)
        self.assertEqual(data["history"]["recorded_count"], 2)
        self.assertEqual(data["history"]["matching_event_count"], 8)
        self.assertIn("recorded proof", data["history"]["summary"])
        self.assertEqual(data["request_context"]["reviewer_note"], "tests passed locally")
        self.assertIn("workspace", data["resource_summary"]["touches"])

    def test_app_export_writes_static_local_app_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "cockpit"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["workspace-init", "--path", tmpdir, "--plan"]), 0)
                self.assertEqual(
                    main(
                        [
                            "agent-add",
                            "app_runner",
                            "--workspace",
                            tmpdir,
                            "--command",
                            f"{sys.executable} -c \"print('app ok')\"",
                            "--capability",
                            "read.workspace",
                            "--allowed-data",
                            "workspace",
                            "--evidence",
                            "command_output",
                            "--force",
                        ]
                    ),
                    0,
                )
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "app-export",
                        "--workspace",
                        tmpdir,
                        "--output",
                        str(output_dir),
                        "--preview-agent",
                        "app_runner",
                        "--preview-note",
                        "operator checked",
                        "--preview-expires-at",
                        "2099-01-01T00:00:00Z",
                        "--json",
                    ]
                )
            data = json.loads(output.getvalue())
            index_html = Path(data["index_html"])
            dashboard_json = Path(data["dashboard_json"])
            state_json = Path(data["state_json"])
            timeline_json = Path(data["timeline_json"])
            preview_json = Path(data["approval_preview_json"])
            html_text = index_html.read_text(encoding="utf-8")
            index_exists = index_html.exists()
            dashboard_exists = dashboard_json.exists()
            state_exists = state_json.exists()
            timeline_exists = timeline_json.exists()
            preview_exists = preview_json.exists()

        self.assertEqual(status, 0)
        self.assertEqual(data["status"], "ready")
        self.assertTrue(index_exists)
        self.assertTrue(dashboard_exists)
        self.assertTrue(state_exists)
        self.assertTrue(timeline_exists)
        self.assertTrue(preview_exists)
        self.assertIn("DelegationHQ Local App", html_text)
        self.assertIn("Control Loop", html_text)
        self.assertIn("Missions", html_text)
        self.assertIn("Approval Inbox", html_text)
        self.assertIn("Evidence", html_text)
        self.assertIn("Settings", html_text)
        self.assertIn("Action intent", html_text)
        self.assertIn("Live effect", html_text)
        self.assertIn("agent-result-ingest", html_text)
        self.assertIn("evidence-ingest", html_text)
        self.assertIn("Request packet", html_text)
        self.assertIn("operator checked", html_text)
        self.assertIn('--review-note &quot;operator checked&quot;', html_text)
        self.assertIn("Timeline", html_text)

    def test_app_export_renders_operator_ux_without_truncating_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "cockpit"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["workspace-init", "--path", tmpdir, "--plan"]), 0)
                self.assertEqual(
                    main(
                        [
                            "agent-add",
                            "ux_runner",
                            "--workspace",
                            tmpdir,
                            "--command",
                            f"{sys.executable} -c \"print('ux ok')\"",
                            "--capability",
                            "read.workspace",
                            "--allowed-data",
                            "workspace",
                            "--evidence",
                            "command_output",
                            "--force",
                        ]
                    ),
                    0,
                )
                for _ in range(4):
                    self.assertEqual(
                        main(
                            [
                                "agent-run",
                                "ux_runner",
                                "--workspace",
                                tmpdir,
                                "--execute",
                                "--confirm",
                                "LOCAL_AGENT_EXECUTION",
                            ]
                        ),
                        0,
                    )
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "app-export",
                        "--workspace",
                        tmpdir,
                        "--output",
                        str(output_dir),
                        "--preview-agent",
                        "ux_runner",
                        "--json",
                    ]
                )
            data = json.loads(output.getvalue())
            html_text = Path(data["index_html"]).read_text(encoding="utf-8")
            timeline_data = json.loads(Path(data["timeline_json"]).read_text(encoding="utf-8"))

        self.assertEqual(status, 0)
        self.assertEqual(timeline_data["shown_count"], timeline_data["event_count"])
        self.assertEqual(timeline_data["event_count"], 16)
        self.assertIn("Showing 16 of 16 event(s).", html_text)
        self.assertIn("1. [gate]", html_text)
        self.assertIn("16. [record]", html_text)
        self.assertIn("data-copy=", html_text)
        self.assertIn("Copy</button>", html_text)
        self.assertIn("Request packet", html_text)
        self.assertIn("Touched resources", html_text)
        self.assertIn("Decision history", html_text)
        self.assertIn("Endpoint:", html_text)
        self.assertIn("Can do:", html_text)
        self.assertIn("Can use:", html_text)
        self.assertIn("Can touch:", html_text)
        self.assertIn("Preview this agent", html_text)
        self.assertIn("delegation approval-preview ux_runner", html_text)
        self.assertIn("Refresh</button>", html_text)
        self.assertIn("<strong>Review timeline</strong>", html_text)
        self.assertNotIn("Functional shell, not the final visual design", html_text)

    def test_app_dashboard_combines_state_preview_and_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["workspace-init", "--path", tmpdir, "--plan"]), 0)
                self.assertEqual(
                    main(
                        [
                            "agent-add",
                            "dashboard_runner",
                            "--workspace",
                            tmpdir,
                            "--command",
                            f"{sys.executable} -c \"print('dashboard ok')\"",
                            "--capability",
                            "read.workspace",
                            "--allowed-data",
                            "workspace",
                            "--evidence",
                            "command_output",
                            "--force",
                        ]
                    ),
                    0,
                )
                self.assertEqual(
                    main(
                        [
                            "agent-run",
                            "dashboard_runner",
                            "--workspace",
                            tmpdir,
                            "--execute",
                            "--confirm",
                            "LOCAL_AGENT_EXECUTION",
                        ]
                    ),
                    0,
                )
            with redirect_stdout(io.StringIO()) as output:
                status = main(["app-dashboard", "--workspace", tmpdir, "--preview-agent", "dashboard_runner", "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["schema_version"], "delegation.app-dashboard.v1")
        self.assertEqual(data["state"]["workspace"]["status"], "ready")
        self.assertEqual(data["approval_preview"]["agent_id"], "dashboard_runner")
        self.assertTrue(data["command_center"])
        self.assertIn("ingest_evidence", [item["id"] for item in data["command_center"]])
        self.assertEqual(
            [step["id"] for step in data["control_loop"]],
            ["workspace", "mission", "agent", "gate", "approval", "execution", "evidence", "timeline_eval"],
        )
        self.assertEqual(data["control_loop"][0]["status"], "ready")
        self.assertEqual(data["control_loop"][6]["status"], "recorded")
        self.assertEqual(
            [area["id"] for area in data["product_areas"]],
            ["missions", "agents", "approval_inbox", "evidence", "settings"],
        )
        self.assertGreaterEqual(data["timeline"]["stage_counts"]["gate"], 1)
        self.assertGreaterEqual(data["timeline"]["stage_counts"]["record"], 1)

    def test_timeline_command_uses_workspace_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["workspace-init", "--path", tmpdir, "--plan"]), 0)
                self.assertEqual(
                    main(
                        [
                            "agent-add",
                            "timeline_runner",
                            "--workspace",
                            tmpdir,
                            "--command",
                            f"{sys.executable} -c \"print('timeline ok')\"",
                            "--capability",
                            "read.workspace",
                            "--allowed-data",
                            "workspace",
                            "--evidence",
                            "command_output",
                            "--force",
                        ]
                    ),
                    0,
                )
                self.assertEqual(
                    main(
                        [
                            "agent-run",
                            "timeline_runner",
                            "--workspace",
                            tmpdir,
                            "--execute",
                            "--confirm",
                            "LOCAL_AGENT_EXECUTION",
                        ]
                    ),
                    0,
                )
            with redirect_stdout(io.StringIO()) as output:
                status = main(["timeline", "--workspace", tmpdir, "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["schema_version"], "delegation.mission-timeline.v1")
        self.assertEqual(data["status"], "recorded")
        self.assertGreaterEqual(data["stage_counts"]["gate"], 1)
        self.assertGreaterEqual(data["stage_counts"]["execute"], 2)
        self.assertGreaterEqual(data["stage_counts"]["record"], 1)

    def test_app_serve_dry_run_reports_local_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["workspace-init", "--path", tmpdir, "--plan"]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["app-serve", "--workspace", tmpdir, "--dry-run", "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["url"], "http://127.0.0.1:8765/")
        self.assertEqual(data["workspace"], str(Path(tmpdir).resolve()))

    def test_app_state_reports_missing_ledger_without_process_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing.jsonl"
            with redirect_stdout(io.StringIO()) as output:
                status = main(["app-state", "--ledger", str(missing), "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["ledger"]["status"], "missing")
        self.assertIn("Ledger does not exist", data["ledger"]["warnings"][0])

    def test_agents_command_shows_harnessfile_passports(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(["agents", str(EXAMPLE)])

        self.assertEqual(status, 0)
        text = output.getvalue()
        self.assertIn("Agent Passport Registry", text)
        self.assertIn("Passports: 4", text)
        self.assertIn("planner: planner", text)
        self.assertIn("runtime: openai.agents", text)

    def test_agents_command_can_print_custom_registry_json(self) -> None:
        registry = ROOT / "examples" / "agent-passports.yaml"
        with redirect_stdout(io.StringIO()) as output:
            status = main(["agents", "--registry", str(registry), "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["passport_count"], 2)
        self.assertIn("crm_update_agent", [passport["id"] for passport in data["passports"]])

    def test_workspace_init_creates_local_first_workspace_and_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "workspace-init",
                        "--path",
                        tmpdir,
                        "--name",
                        "QA Local Workspace",
                        "--owner",
                        "Ammar",
                        "--plan",
                        "--json",
                    ]
                )
            data = json.loads(output.getvalue())
            harnessfile = Path(data["harnessfile"])
            registry = Path(data["registry"])
            ledger = Path(data["ledger"])
            harness_exists = harnessfile.exists()
            registry_exists = registry.exists()
            ledger_exists = ledger.exists()
            with redirect_stdout(io.StringIO()) as status_output:
                status_check = main(["workspace-status", "--path", tmpdir, "--json"])
            status_data = json.loads(status_output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["status"], "ready")
        self.assertTrue(data["planned"])
        self.assertEqual(data["agent_count"], 1)
        self.assertTrue(harness_exists)
        self.assertTrue(registry_exists)
        self.assertTrue(ledger_exists)
        self.assertEqual(status_check, 0)
        self.assertEqual(status_data["status"], "ready")
        self.assertEqual(status_data["agent_count"], 1)
        self.assertEqual(status_data["harness_status"], "ready")
        self.assertEqual(status_data["registry_status"], "ready")
        self.assertEqual(status_data["ledger_status"], "ready")

    def test_workspace_init_is_human_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with redirect_stdout(io.StringIO()) as output:
                status = main(["workspace-init", "--path", tmpdir, "--plan"])

        self.assertEqual(status, 0)
        text = output.getvalue()
        self.assertIn("Local Workspace Created", text)
        self.assertIn("GitHub required: false", text)
        self.assertIn("This folder is now an AI workspace.", text)

    def test_agent_add_registers_custom_cli_agent_without_yaml_editing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = Path(tmpdir) / ".delegation" / "agents.yaml"
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "agent-add",
                        "research_agent",
                        "--registry",
                        str(registry),
                        "--command",
                        "python agents/research_agent.py",
                        "--capability",
                        "read.workspace",
                        "--allowed-data",
                        "workspace",
                        "--evidence",
                        "command_output",
                        "--json",
                    ]
                )
            data = json.loads(output.getvalue())
            with redirect_stdout(io.StringIO()) as agents_output:
                agents_status = main(["agents", "--registry", str(registry), "--json"])
            agents_data = json.loads(agents_output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["agent_id"], "research_agent")
        self.assertEqual(data["endpoint"], {"type": "command", "value": "python agents/research_agent.py"})
        self.assertEqual(agents_status, 0)
        self.assertEqual(agents_data["status"], "ready")
        self.assertIn("research_agent", [passport["id"] for passport in agents_data["passports"]])

    def test_agent_add_blocks_duplicate_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = Path(tmpdir) / "agents.yaml"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(["agent-add", "cli_agent", "--registry", str(registry), "--command", "python agent.py"]),
                    0,
                )
            with redirect_stderr(io.StringIO()) as error:
                status = main(["agent-add", "cli_agent", "--registry", str(registry), "--command", "python agent.py"])

        self.assertEqual(status, 1)
        self.assertIn("already exists", error.getvalue())

    def test_agent_run_executes_command_agent_and_records_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = Path(tmpdir) / ".delegation" / "agents.yaml"
            ledger = Path(tmpdir) / ".delegation" / "agent-run.jsonl"
            command = f"{sys.executable} -c \"print('agent ok')\""
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "agent-add",
                            "runner_agent",
                            "--registry",
                            str(registry),
                            "--command",
                            command,
                            "--capability",
                            "read.workspace",
                            "--allowed-data",
                            "workspace",
                            "--evidence",
                            "command_output",
                        ]
                    ),
                    0,
                )
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "agent-run",
                        "runner_agent",
                        "--registry",
                        str(registry),
                        "--ledger",
                        str(ledger),
                        "--action",
                        "read.workspace",
                        "--target",
                        "workspace",
                        "--execute",
                        "--confirm",
                        "LOCAL_AGENT_EXECUTION",
                        "--cwd",
                        tmpdir,
                        "--json",
                    ]
                )
            data = json.loads(output.getvalue())
            events = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
            event_types = [event["type"] for event in events]
            artifact_path = Path(data["output_artifact"])
            artifact_exists = artifact_path.exists()
            with redirect_stdout(io.StringIO()) as audit_output:
                audit_status = main(["agent-audit", "--ledger", str(ledger), "--json"])
            audit_data = json.loads(audit_output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["status"], "recorded")
        self.assertTrue(data["executed"])
        self.assertEqual(data["returncode"], 0)
        self.assertIn("agent ok", data["stdout_tail"])
        self.assertTrue(artifact_exists)
        self.assertIn("agent.gate.previewed", event_types)
        self.assertIn("agent.execution.completed", event_types)
        self.assertIn("runprint.recording.completed", event_types)
        self.assertEqual(audit_status, 0)
        self.assertEqual(audit_data["status"], "recorded")

    def test_agent_add_and_run_use_workspace_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            command = f"{sys.executable} -c \"print('workspace agent ok')\""
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["workspace-init", "--path", tmpdir, "--plan"]), 0)
                self.assertEqual(
                    main(
                        [
                            "agent-add",
                            "workspace_runner",
                            "--workspace",
                            tmpdir,
                            "--command",
                            command,
                            "--capability",
                            "read.workspace",
                            "--allowed-data",
                            "workspace",
                            "--evidence",
                            "command_output",
                            "--force",
                        ]
                    ),
                    0,
                )
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "agent-run",
                        "workspace_runner",
                        "--workspace",
                        tmpdir,
                        "--execute",
                        "--confirm",
                        "LOCAL_AGENT_EXECUTION",
                        "--json",
                    ]
                )
            data = json.loads(output.getvalue())
            ledger = Path(tmpdir) / ".delegation" / "agent-run.jsonl"
            artifact = Path(data["output_artifact"])
            ledger_exists = ledger.exists()
            artifact_exists = artifact.exists()

        self.assertEqual(status, 0)
        self.assertEqual(data["status"], "recorded")
        self.assertEqual(data["action"], "read.workspace")
        self.assertEqual(data["target"], "workspace")
        self.assertIn("workspace agent ok", data["stdout_tail"])
        self.assertTrue(ledger_exists)
        self.assertTrue(artifact_exists)

    def test_agent_run_requires_exact_confirmation_for_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = Path(tmpdir) / "agents.yaml"
            ledger = Path(tmpdir) / "agent-run.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "agent-add",
                            "runner_agent",
                            "--registry",
                            str(registry),
                            "--command",
                            f"{sys.executable} -c \"print('nope')\"",
                            "--capability",
                            "read.workspace",
                            "--allowed-data",
                            "workspace",
                            "--evidence",
                            "command_output",
                        ]
                    ),
                    0,
                )
            with redirect_stderr(io.StringIO()) as error:
                status = main(
                    [
                        "agent-run",
                        "runner_agent",
                        "--registry",
                        str(registry),
                        "--ledger",
                        str(ledger),
                        "--action",
                        "read.workspace",
                        "--target",
                        "workspace",
                        "--execute",
                    ]
                )

        self.assertEqual(status, 1)
        self.assertIn("LOCAL_AGENT_EXECUTION", error.getvalue())
        self.assertFalse(ledger.exists())

    def test_agent_gate_command_previews_harnessfile_agent(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(
                [
                    "agent-gate",
                    str(EXAMPLE),
                    "implementer",
                    "--action",
                    "create_pull_request",
                    "--target",
                    "repository",
                ]
            )

        self.assertEqual(status, 0)
        text = output.getvalue()
        self.assertIn("Agent Gate", text)
        self.assertIn("Decision: approval_required", text)
        self.assertIn("write.pull_request_draft", text)

    def test_agent_gate_command_can_print_custom_registry_json(self) -> None:
        registry = ROOT / "examples" / "agent-passports.yaml"
        with redirect_stdout(io.StringIO()) as output:
            status = main(
                [
                    "agent-gate",
                    "--registry",
                    str(registry),
                    "crm_update_agent",
                    "--action",
                    "crm.write",
                    "--target",
                    "crm.accounts",
                    "--json",
                ]
            )
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["schema_version"], "delegation.agent-gate.v1")
        self.assertEqual(data["decision"], "approval_required")
        self.assertEqual(data["matched_approvals"], ["crm.write"])

    def test_agent_gate_command_blocks_wrong_agent(self) -> None:
        with redirect_stdout(io.StringIO()):
            status = main(
                [
                    "agent-gate",
                    str(EXAMPLE),
                    "planner",
                    "--action",
                    "create_pull_request",
                    "--target",
                    "repository",
                    "--approval",
                    "pull_request",
                    "--json",
                ]
            )

        self.assertEqual(status, 1)

    def test_agent_gate_command_can_write_ledger_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(
                    [
                        "agent-gate",
                        str(EXAMPLE),
                        "implementer",
                        "--action",
                        "create_pull_request",
                        "--target",
                        "repository",
                        "--approval",
                        "pull_request",
                        "--ledger",
                        str(ledger),
                        "--write",
                    ]
                )
            events = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(status, 0)
        self.assertIn("Agent Gate event appended", output.getvalue())
        self.assertEqual(events[-1]["type"], "agent.gate.previewed")
        self.assertEqual(events[-1]["status"], "allow")
        self.assertEqual(events[-1]["details"]["agent_gate"]["decision"], "allow")

    def test_agent_audit_reports_ready_for_recording(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
                self.assertEqual(
                    main(
                        [
                            "agent-gate",
                            str(EXAMPLE),
                            "implementer",
                            "--action",
                            "create_pull_request",
                            "--target",
                            "repository",
                            "--approval",
                            "pull_request",
                            "--ledger",
                            str(ledger),
                            "--write",
                        ]
                    ),
                    0,
                )
            with redirect_stdout(io.StringIO()) as output:
                status = main(["agent-audit", "--ledger", str(ledger), "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["status"], "ready_for_recording")
        self.assertEqual(data["gate_count"], 1)
        self.assertEqual(data["runprint_bundle_count"], 1)
        self.assertEqual(data["items"][0]["outcome"], "recording_planned")

    def test_agent_audit_blocks_missing_gate_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["agent-audit", "--ledger", str(ledger), "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 1)
        self.assertEqual(data["status"], "missing_gate")
        self.assertEqual(data["gate_count"], 0)
        self.assertEqual(data["runprint_bundle_count"], 1)

    def test_approval_inbox_reports_pending_gate_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
                self.assertEqual(
                    main(
                        [
                            "agent-gate",
                            str(EXAMPLE),
                            "implementer",
                            "--action",
                            "create_pull_request",
                            "--target",
                            "repository",
                            "--ledger",
                            str(ledger),
                            "--write",
                        ]
                    ),
                    0,
                )
            with redirect_stdout(io.StringIO()) as output:
                status = main(["approval-inbox", "--ledger", str(ledger), "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["status"], "needs_attention")
        self.assertEqual(data["pending_count"], 1)
        self.assertEqual(data["items"][0]["status"], "pending_approval")

    def test_approval_decision_command_appends_human_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            action_id = "agent_gate.implementer.create_pull_request"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
                self.assertEqual(
                    main(
                        [
                            "agent-gate",
                            str(EXAMPLE),
                            "implementer",
                            "--action",
                            "create_pull_request",
                            "--target",
                            "repository",
                            "--ledger",
                            str(ledger),
                            "--write",
                        ]
                    ),
                    0,
                )
            with redirect_stdout(io.StringIO()) as receipt_output:
                receipt_status = main(
                    [
                        "approval-decision",
                        "--ledger",
                        str(ledger),
                        "--action-id",
                        action_id,
                        "--decision",
                        "approve",
                        "--approver",
                        "Ammar",
                        "--reason",
                        "Scoped and evidence is planned.",
                    ]
                )
            with redirect_stdout(io.StringIO()) as inbox_output:
                inbox_status = main(["approval-inbox", "--ledger", str(ledger), "--json"])
        data = json.loads(inbox_output.getvalue())

        self.assertEqual(receipt_status, 0)
        self.assertIn("Approval decision appended", receipt_output.getvalue())
        self.assertEqual(inbox_status, 0)
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["approved_count"], 1)
        self.assertEqual(data["items"][0]["latest_decision"]["approver"], "Ammar")

    def test_runprint_ingest_marks_gate_audit_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            action_id = "agent_gate.implementer.create_pull_request"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
                self.assertEqual(
                    main(
                        [
                            "agent-gate",
                            str(EXAMPLE),
                            "implementer",
                            "--action",
                            "create_pull_request",
                            "--target",
                            "repository",
                            "--approval",
                            "pull_request",
                            "--ledger",
                            str(ledger),
                            "--write",
                        ]
                    ),
                    0,
                )
            with redirect_stdout(io.StringIO()) as ingest_output:
                ingest_status = main(
                    [
                        "runprint-ingest",
                        "--ledger",
                        str(ledger),
                        "--action-id",
                        action_id,
                        "--recording-id",
                        "rec-cli",
                        "--bundle-id",
                        "bundle-cli",
                        "--artifact",
                        "run-ledger:jsonl:.delegation/demo.jsonl",
                        "--summary",
                        "Recorded CLI smoke evidence.",
                    ]
                )
            with redirect_stdout(io.StringIO()) as audit_output:
                audit_status = main(["agent-audit", "--ledger", str(ledger), "--json"])
            with redirect_stdout(io.StringIO()) as inbox_output:
                inbox_status = main(["approval-inbox", "--ledger", str(ledger), "--json"])
        audit = json.loads(audit_output.getvalue())
        inbox = json.loads(inbox_output.getvalue())

        self.assertEqual(ingest_status, 0)
        self.assertIn("RunPrint evidence appended", ingest_output.getvalue())
        self.assertEqual(audit_status, 0)
        self.assertEqual(audit["status"], "recorded")
        self.assertEqual(audit["items"][0]["evidence_status"], "recorded")
        self.assertEqual(inbox_status, 0)
        self.assertEqual(inbox["items"][0]["status"], "recorded")

    def test_evidence_ingest_marks_gate_audit_recorded_for_any_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            action_id = "agent_gate.implementer.create_pull_request"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
                self.assertEqual(
                    main(
                        [
                            "agent-gate",
                            str(EXAMPLE),
                            "implementer",
                            "--action",
                            "create_pull_request",
                            "--target",
                            "repository",
                            "--approval",
                            "pull_request",
                            "--ledger",
                            str(ledger),
                            "--write",
                        ]
                    ),
                    0,
                )
            with redirect_stdout(io.StringIO()) as ingest_output:
                ingest_status = main(
                    [
                        "evidence-ingest",
                        "--ledger",
                        str(ledger),
                        "--tool",
                        "test-reporter",
                        "--tool-kind",
                        "test",
                        "--action-id",
                        action_id,
                        "--recording-id",
                        "rec-cli-test",
                        "--bundle-id",
                        "bundle-cli-test",
                        "--artifact",
                        "pytest:junit:artifacts/pytest.xml",
                        "--summary",
                        "Recorded generic CLI evidence.",
                    ]
                )
            with redirect_stdout(io.StringIO()) as audit_output:
                audit_status = main(["agent-audit", "--ledger", str(ledger), "--json"])
            with redirect_stdout(io.StringIO()) as evidence_output:
                evidence_status = main(["evidence", "--ledger", str(ledger), "--json"])
            audit = json.loads(audit_output.getvalue())
            evidence = json.loads(evidence_output.getvalue())

        self.assertEqual(ingest_status, 0)
        self.assertIn("Evidence appended", ingest_output.getvalue())
        self.assertEqual(audit_status, 0)
        self.assertEqual(audit["status"], "recorded")
        self.assertEqual(audit["recorded_evidence_count"], 1)
        self.assertEqual(evidence_status, 0)
        self.assertEqual(evidence["recorded_count"], 1)
        self.assertEqual(evidence["recordings"][0]["evidence_tool"], "test-reporter")

    def test_agent_result_ingest_records_custom_agent_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            result_path = Path(tmpdir) / "agent-result.json"
            action_id = "agent_gate.implementer.create_pull_request"
            result_path.write_text(
                json.dumps(
                    {
                        "schema_version": "delegation.agent-result.v1",
                        "action_id": action_id,
                        "agent_id": "implementer",
                        "status": "completed",
                        "summary": "Custom agent opened the pull request draft under control.",
                        "changed_resources": ["repository"],
                        "runprint_recording_id": "rec-agent-result",
                        "evidence_bundle_id": "bundle-agent-result",
                        "artifacts": [{"id": "run-ledger", "kind": "jsonl", "path": ".delegation/demo.jsonl"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
                self.assertEqual(
                    main(
                        [
                            "agent-gate",
                            str(EXAMPLE),
                            "implementer",
                            "--action",
                            "create_pull_request",
                            "--target",
                            "repository",
                            "--approval",
                            "pull_request",
                            "--ledger",
                            str(ledger),
                            "--write",
                        ]
                    ),
                    0,
                )
            with redirect_stdout(io.StringIO()) as ingest_output:
                ingest_status = main(
                    [
                        "agent-result-ingest",
                        "--ledger",
                        str(ledger),
                        "--action-id",
                        action_id,
                        "--result",
                        str(result_path),
                    ]
                )
            with redirect_stdout(io.StringIO()) as audit_output:
                audit_status = main(["agent-audit", "--ledger", str(ledger), "--json"])
            events = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        audit = json.loads(audit_output.getvalue())

        self.assertEqual(ingest_status, 0)
        self.assertIn("Agent result appended", ingest_output.getvalue())
        self.assertIn("agent.result.reported", [event["type"] for event in events])
        self.assertTrue(
            any(
                event["type"] == "runprint.recording.completed"
                and event["details"]["adapter"] == "runprint.agent_result"
                for event in events
            )
        )
        self.assertEqual(audit_status, 0)
        self.assertEqual(audit["status"], "recorded")

    def test_agent_result_ingest_blocks_wrong_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            result_path = Path(tmpdir) / "agent-result.json"
            action_id = "agent_gate.implementer.create_pull_request"
            result_path.write_text(
                json.dumps(
                    {
                        "schema_version": "delegation.agent-result.v1",
                        "action_id": action_id,
                        "agent_id": "other_agent",
                        "status": "completed",
                        "summary": "Wrong agent tried to report work.",
                        "changed_resources": ["repository"],
                        "runprint_recording_id": "rec-wrong-agent",
                        "evidence_bundle_id": "bundle-wrong-agent",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
                self.assertEqual(
                    main(
                        [
                            "agent-gate",
                            str(EXAMPLE),
                            "implementer",
                            "--action",
                            "create_pull_request",
                            "--target",
                            "repository",
                            "--approval",
                            "pull_request",
                            "--ledger",
                            str(ledger),
                            "--write",
                        ]
                    ),
                    0,
                )
            before = ledger.read_text(encoding="utf-8")
            with redirect_stdout(io.StringIO()) as ingest_output:
                ingest_status = main(
                    [
                        "agent-result-ingest",
                        "--ledger",
                        str(ledger),
                        "--action-id",
                        action_id,
                        "--result",
                        str(result_path),
                        "--json",
                    ]
                )
            after = ledger.read_text(encoding="utf-8")
        data = json.loads(ingest_output.getvalue())

        self.assertEqual(ingest_status, 1)
        self.assertEqual(data["status"], "invalid_result")
        self.assertTrue(any("does not match" in warning for warning in data["warnings"]))
        self.assertEqual(before, after)

    def test_app_state_can_include_agent_gate_preview(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(
                [
                    "app-state",
                    "--harnessfile",
                    str(EXAMPLE),
                    "--gate-agent",
                    "implementer",
                    "--gate-action",
                    "create_pull_request",
                    "--gate-target",
                    "repository",
                    "--json",
                ]
            )
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["agent_gate"]["decision"], "approval_required")
        self.assertEqual(data["agent_gate"]["preview_count"], 1)
        self.assertEqual(data["agent_gate"]["agent_id"], "implementer")

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
        source = ROOT / "examples" / "ledgers" / "feedback-recovery-ready.jsonl"
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "feedback-recovery.jsonl"
            harnessfile = Path(tmpdir) / "feedback-harness.json"
            ledger.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
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

    def test_apply_feedback_previews_recovery_comment(self) -> None:
        source = ROOT / "examples" / "ledgers" / "feedback-recovery-ready.jsonl"
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "feedback-recovery.jsonl"
            harnessfile = Path(tmpdir) / "feedback-harness.json"
            ledger.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
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
                status = main(["apply-feedback", str(harnessfile), "--ledger", str(ledger)])

        self.assertEqual(status, 0)
        self.assertIn("GitHub Feedback Apply Gate", output.getvalue())
        self.assertIn("Status: ready", output.getvalue())
        self.assertIn("Rerun with `--apply --confirm LIVE_FEEDBACK_ISSUES`", output.getvalue())

    def test_apply_feedback_github_app_auth_blocks_without_config(self) -> None:
        source = ROOT / "examples" / "ledgers" / "feedback-recovery-ready.jsonl"
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "feedback-recovery.jsonl"
            harnessfile = Path(tmpdir) / "feedback-harness.json"
            ledger.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
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
            with patch.dict("os.environ", {}, clear=True):
                with redirect_stdout(io.StringIO()) as output:
                    status = main(
                        [
                            "apply-feedback",
                            str(harnessfile),
                            "--ledger",
                            str(ledger),
                            "--apply",
                            "--confirm",
                            "LIVE_FEEDBACK_ISSUES",
                            "--auth",
                            "github-app",
                        ]
                    )

        self.assertEqual(status, 1)
        self.assertIn("GitHub App auth is missing", output.getvalue())

    def test_apply_feedback_no_action_does_not_require_github_app_auth(self) -> None:
        source = ROOT / "examples" / "ledgers" / "feedback-recovery.jsonl"
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "feedback-recovery.jsonl"
            harnessfile = Path(tmpdir) / "feedback-harness.json"
            ledger.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
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
            with patch.dict("os.environ", {}, clear=True):
                with redirect_stdout(io.StringIO()) as output:
                    status = main(
                        [
                            "apply-feedback",
                            str(harnessfile),
                            "--ledger",
                            str(ledger),
                            "--apply",
                            "--confirm",
                            "LIVE_FEEDBACK_ISSUES",
                            "--auth",
                            "github-app",
                        ]
                    )

        self.assertEqual(status, 0)
        self.assertIn("Status: no_action", output.getvalue())
        self.assertIn("no token was minted", output.getvalue())

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

    def test_evidence_command_summarizes_runprint_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["evidence", "--ledger", str(ledger)])

        self.assertEqual(status, 0)
        self.assertIn("Evidence Bundle Report", output.getvalue())
        self.assertIn("Bundles: 1", output.getvalue())
        self.assertIn("executor.evidence_recorder", output.getvalue())
        self.assertIn("run-ledger", output.getvalue())

    def test_evidence_command_can_print_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", str(EXAMPLE), "--ledger", str(ledger)]), 0)
            with redirect_stdout(io.StringIO()) as output:
                status = main(["evidence", "--ledger", str(ledger), "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["bundle_count"], 1)
        self.assertEqual(data["bundle_plans"][0]["action_id"], "executor.evidence_recorder")
        self.assertEqual(data["bundle_plans"][0]["artifacts"][0]["id"], "run-ledger")

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
        self.assertIn("Status: ready", output.getvalue())
        self.assertIn("delegation demo", output.getvalue())
        self.assertIn("Suggest Loop", output.getvalue())

    def test_doctor_command_can_print_json(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(["doctor", "--skip-github", "--json"])
        data = json.loads(output.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(data["failed_count"], 0)
        self.assertTrue(any(check["id"] == "suggest_loop" for check in data["checks"]))

    def test_doctor_command_can_include_github_app_diagnostics(self) -> None:
        with patch.dict("os.environ", {}, clear=True), redirect_stdout(io.StringIO()) as output:
            status = main(["doctor", "--skip-github", "--github-app"])

        self.assertEqual(status, 0)
        self.assertIn("GitHub App Auth", output.getvalue())
        self.assertIn("No DELEGATION_GITHUB_APP_* env vars were found.", output.getvalue())

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

    def test_cancel_actions_preview_is_safe(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(["cancel-actions", "AmmarAlBalkhi/delegation-bot", "123"])

        self.assertEqual(status, 0)
        self.assertIn("GitHub Actions Cancel Gate", output.getvalue())
        self.assertIn("Status: ready", output.getvalue())
        self.assertIn("CANCEL_GITHUB_ACTIONS", output.getvalue())

    def test_cancel_actions_live_mode_blocks_without_token(self) -> None:
        with redirect_stdout(io.StringIO()) as output:
            status = main(
                [
                    "cancel-actions",
                    "AmmarAlBalkhi/delegation-bot",
                    "123",
                    "--apply",
                    "--confirm",
                    "CANCEL_GITHUB_ACTIONS",
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
