from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from delegation_bot.harness_plan import build_dry_run_ledger, compile_plan, render_plan, write_jsonl


VALID_MANIFEST = {
    "version": "delegation.ai/v1",
    "id": "ai-harness-control-plane",
    "objective": "Coordinate AI harnesses with policy and evidence.",
    "triggers": [{"type": "workflow_dispatch"}],
    "capability_packs": [
        {
            "id": "repo_reader",
            "description": "Read repo context.",
            "capabilities": ["read.repository"],
        },
        {
            "id": "pull_request_drafter",
            "description": "Draft pull requests.",
            "capabilities": ["write.pull_request_draft"],
        },
    ],
    "models": [
        {"id": "planner_model", "provider": "openai", "model": "gpt-5.5", "role": "planning"}
    ],
    "agents": [
        {
            "id": "planner",
            "runtime": "openai.agents",
            "model": "planner_model",
            "autonomy_level": "draft",
            "capability_packs": ["repo_reader"],
        },
        {
            "id": "implementer",
            "runtime": "codex.thread",
            "model": "planner_model",
            "autonomy_level": "act",
            "capability_packs": ["repo_reader", "pull_request_drafter"],
        },
    ],
    "executors": [
        {
            "id": "agent",
            "kind": "ai_harness",
            "adapter": "codex.thread",
            "model": "planner_model",
            "purpose": "Implement approved scoped changes.",
        }
    ],
    "context": {"sources": [{"id": "repository", "kind": "git", "trust": "high"}]},
    "policies": {
        "approvals": {"required_for": ["agent_execution", "pull_request"]},
        "budgets": {"max_usd_per_run": 10},
        "permissions": {"network": "restricted"},
    },
    "outputs": ["github.pull_request", "run_ledger"],
    "evals": [{"id": "tests_pass", "type": "quality_gate"}],
}


class HarnessPlanTests(unittest.TestCase):
    def test_compile_plan_includes_models_executors_policies_outputs_and_evals(self) -> None:
        plan = compile_plan(VALID_MANIFEST, source="Harnessfile.yaml")
        action_types = [action.type for action in plan.actions]

        self.assertIn("trigger.observe", action_types)
        self.assertIn("context.load", action_types)
        self.assertIn("capability_pack.register", action_types)
        self.assertIn("model.configure", action_types)
        self.assertIn("agent.passport", action_types)
        self.assertIn("adapter.codex.thread.prepare", action_types)
        self.assertIn("policy.approval_gate", action_types)
        self.assertIn("policy.budget_gate", action_types)
        self.assertIn("policy.permission_gate", action_types)
        self.assertIn("output.prepare.github.pull_request", action_types)
        self.assertIn("eval.schedule", action_types)

    def test_executor_plan_includes_adapter_contract(self) -> None:
        plan = compile_plan(VALID_MANIFEST, source="Harnessfile.yaml")
        executor_action = next(action for action in plan.actions if action.id == "executor.agent")
        contract = executor_action.metadata["adapter_contract"]

        self.assertEqual(executor_action.adapter, "codex.thread")
        self.assertEqual(executor_action.risk, "medium")
        self.assertTrue(executor_action.requires_approval)
        self.assertEqual(contract["id"], "codex.thread")
        self.assertIn("qa_result", contract["required_evidence"])
        self.assertEqual(plan.warnings, ())

    def test_unknown_executor_adapter_adds_warning(self) -> None:
        manifest = dict(VALID_MANIFEST)
        manifest["executors"] = [
            {**VALID_MANIFEST["executors"][0], "adapter": "unknown.harness"}
        ]

        plan = compile_plan(manifest, source="Harnessfile.yaml")

        self.assertIn("No built-in adapter contract found for `unknown.harness`.", plan.warnings)

    def test_render_plan_is_readable(self) -> None:
        plan = compile_plan(VALID_MANIFEST, source="Harnessfile.yaml")
        text = render_plan(plan)

        self.assertIn("Plan: ai-harness-control-plane", text)
        self.assertIn("Mode: dry-run", text)
        self.assertIn("Prepare agent passport `implementer`", text)
        self.assertIn("Prepare executor `agent`", text)
        self.assertIn("approval-required", text)

    def test_ledger_events_are_jsonl_serializable(self) -> None:
        plan = compile_plan(VALID_MANIFEST, source="Harnessfile.yaml")
        events = build_dry_run_ledger(
            plan,
            run_id="dryrun-test",
            timestamp="2026-07-03T20:00:00+00:00",
        )

        self.assertEqual(events[0].type, "plan.compiled")
        self.assertEqual(events[-1].type, "dry_run.completed")
        self.assertEqual([event.sequence for event in events], list(range(1, len(events) + 1)))
        self.assertIn("adapter.codex.thread.prepare", {event.type for event in events})
        self.assertIn("codex.thread.planned", {event.type for event in events})

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.jsonl"
            write_jsonl(events, path)
            lines = path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), len(events))
        self.assertEqual(json.loads(lines[0])["run_id"], "dryrun-test")

    def test_sdk_backed_adapter_events_include_result_evidence(self) -> None:
        manifest = dict(VALID_MANIFEST)
        manifest["executors"] = [
            {
                "id": "issue_planner",
                "kind": "workflow",
                "adapter": "github.issue",
                "purpose": "Convert validated plans into GitHub Issues.",
                "inputs": {
                    "repository": "AmmarAlBalkhi/delegation-bot",
                    "issue_title": "Plan the adapter SDK",
                    "issue_body": "Capture the dry-run adapter result.",
                },
            }
        ]
        plan = compile_plan(manifest, source="Harnessfile.yaml")
        events = build_dry_run_ledger(
            plan,
            run_id="dryrun-test",
            timestamp="2026-07-03T20:00:00+00:00",
        )

        issue_event = next(event for event in events if event.type == "github.issue.planned")

        self.assertEqual(issue_event.status, "planned")
        self.assertTrue(issue_event.details["issue_marker"].startswith("delegation-bot:"))
        self.assertEqual(issue_event.details["adapter_result"]["status"], "planned")
        self.assertIn("github.issue", issue_event.details["adapter_result"]["outputs"])

    def test_sample_echo_adapter_events_include_result_evidence(self) -> None:
        manifest = dict(VALID_MANIFEST)
        manifest["executors"] = [
            {
                "id": "sample_echo",
                "kind": "tool",
                "adapter": "sample.echo",
                "purpose": "Demonstrate the adapter SDK without network calls.",
                "inputs": {
                    "message": "No network required.",
                    "label": "unit-test",
                },
            }
        ]
        plan = compile_plan(manifest, source="Harnessfile.yaml")
        events = build_dry_run_ledger(
            plan,
            run_id="dryrun-test",
            timestamp="2026-07-03T20:00:00+00:00",
        )

        echo_event = next(event for event in events if event.type == "sample.echo.planned")

        self.assertEqual(echo_event.status, "planned")
        self.assertEqual(echo_event.details["label"], "unit-test")
        self.assertEqual(echo_event.details["adapter_result"]["status"], "planned")
        self.assertIn("sample.echo", echo_event.details["adapter_result"]["outputs"])
        self.assertIn("echo_hash", echo_event.details["adapter_result"]["evidence"])


if __name__ == "__main__":
    unittest.main()
