from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from delegation_bot.evals import (
    eval_approvals_before_risky_actions,
    eval_mcp_tool_risk_review,
    eval_required_adapter_evidence,
    eval_results_to_events,
    eval_tests_pass_before_pr,
    eval_ledger_is_valid,
    eval_no_duplicate_issue_markers,
    load_jsonl,
    run_declared_evals,
)


MANIFEST = {
    "evals": [
        {"id": "no_duplicate_issue_markers", "type": "invariant"},
        {"id": "approvals_before_risky_actions", "type": "policy"},
        {"id": "required_adapter_evidence", "type": "invariant"},
        {"id": "mcp_tool_risk_review", "type": "policy"},
        {"id": "tests_pass_before_pr", "type": "quality_gate"},
    ]
}


VALID_LEDGER = [
    {
        "run_id": "run-1",
        "sequence": 1,
        "timestamp": "2026-07-03T20:00:00+00:00",
        "type": "plan.compiled",
        "status": "planned",
        "message": "Compiled.",
        "action_id": None,
        "details": {},
    }
]


ADAPTER_RESULT_LEDGER = [
    VALID_LEDGER[0],
    {
        "run_id": "run-1",
        "sequence": 2,
        "timestamp": "2026-07-03T20:00:00+00:00",
        "type": "github.issue.planned",
        "status": "planned",
        "message": "Planned issue.",
        "action_id": "executor.issue_planner",
        "details": {
            "adapter": "github.issue",
            "adapter_result": {
                "status": "planned",
                "message": "Dry-run planned.",
                "outputs": {"github.issue": {"title": "Demo"}},
                "evidence": {"issue_marker": "delegation-bot:abc123"},
                "dry_run": True,
            },
        },
    },
]

MCP_TOOL_LEDGER = [
    VALID_LEDGER[0],
    {
        "run_id": "run-1",
        "sequence": 2,
        "timestamp": "2026-07-03T20:00:00+00:00",
        "type": "mcp.tool.planned",
        "status": "planned",
        "message": "Planned MCP tool.",
        "action_id": "executor.tool_probe",
        "details": {
            "adapter": "mcp.tool",
            "adapter_result": {
                "status": "planned",
                "message": "Dry-run planned.",
                "outputs": {
                    "tool_result": {
                        "server": "local-repository-tools",
                        "tool_name": "inspect_repository",
                        "planned_result_id": "fixture-tool-result",
                    }
                },
                "evidence": {
                    "tool_name": "inspect_repository",
                    "tool_result": "fixture-tool-result",
                    "permission_scope": "filesystem_read",
                    "risk_level": "low",
                    "prompt_injection_risk": "low",
                    "recommended_gate": "none",
                },
                "dry_run": True,
            },
        },
    },
]


class EvalTests(unittest.TestCase):
    def test_ledger_is_valid_passes_for_contiguous_events(self) -> None:
        result = eval_ledger_is_valid(VALID_LEDGER)

        self.assertEqual(result.status, "passed")

    def test_approval_eval_fails_for_unapproved_executed_risky_action(self) -> None:
        result = eval_approvals_before_risky_actions(
            [
                {
                    **VALID_LEDGER[0],
                    "sequence": 1,
                    "type": "adapter.example.executed",
                    "status": "executed",
                    "action_id": "action.risky",
                    "details": {"action": {"risk": "high", "requires_approval": True}},
                }
            ]
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.details["violations"], ["action.risky"])

    def test_tests_before_pr_blocks_without_executed_pr(self) -> None:
        result = eval_tests_pass_before_pr(VALID_LEDGER)

        self.assertEqual(result.status, "blocked")

    def test_tests_before_pr_passes_with_prior_test_event(self) -> None:
        result = eval_tests_pass_before_pr(
            [
                {**VALID_LEDGER[0], "sequence": 1, "type": "test.passed", "status": "passed"},
                {
                    **VALID_LEDGER[0],
                    "sequence": 2,
                    "type": "github.pull_request.opened",
                    "status": "executed",
                    "action_id": "pr.1",
                },
            ]
        )

        self.assertEqual(result.status, "passed")

    def test_duplicate_issue_marker_allows_same_action_lifecycle(self) -> None:
        result = eval_no_duplicate_issue_markers(
            [
                {
                    **VALID_LEDGER[0],
                    "sequence": 1,
                    "type": "github.issue.planned",
                    "action_id": "executor.issue_planner",
                    "details": {"issue_marker": "delegation-bot:abc123"},
                },
                {
                    **VALID_LEDGER[0],
                    "sequence": 2,
                    "type": "github.issue.created",
                    "status": "executed",
                    "action_id": "executor.issue_planner",
                    "details": {"issue_marker": "delegation-bot:abc123"},
                },
            ]
        )

        self.assertEqual(result.status, "passed")

    def test_duplicate_issue_marker_fails_across_multiple_actions(self) -> None:
        result = eval_no_duplicate_issue_markers(
            [
                {
                    **VALID_LEDGER[0],
                    "sequence": 1,
                    "type": "github.issue.planned",
                    "action_id": "executor.issue_one",
                    "details": {"issue_marker": "delegation-bot:abc123"},
                },
                {
                    **VALID_LEDGER[0],
                    "sequence": 2,
                    "type": "github.issue.planned",
                    "action_id": "executor.issue_two",
                    "details": {"issue_marker": "delegation-bot:abc123"},
                },
            ]
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.details["duplicates"], ["delegation-bot:abc123"])

    def test_duplicate_issue_marker_allows_feedback_update_lifecycle(self) -> None:
        marker = "delegation-bot:eval:required_adapter_evidence:abc123"
        result = eval_no_duplicate_issue_markers(
            [
                {
                    **VALID_LEDGER[0],
                    "sequence": 1,
                    "type": "github.issue.planned",
                    "action_id": "feedback.create.required_adapter_evidence.abc123",
                    "details": {"issue_marker": marker, "feedback": {"marker": marker, "operation": "create"}},
                },
                {
                    **VALID_LEDGER[0],
                    "sequence": 2,
                    "type": "github.issue.created",
                    "status": "executed",
                    "action_id": "feedback.create.required_adapter_evidence.abc123",
                    "details": {"issue_marker": marker, "issue_number": 17},
                },
                {
                    **VALID_LEDGER[0],
                    "sequence": 3,
                    "type": "github.issue.planned",
                    "action_id": "feedback.update.required_adapter_evidence.abc123",
                    "details": {"issue_marker": marker, "feedback": {"marker": marker, "operation": "update"}},
                },
            ]
        )

        self.assertEqual(result.status, "passed")

    def test_required_adapter_evidence_passes_for_sdk_adapter_result(self) -> None:
        result = eval_required_adapter_evidence(ADAPTER_RESULT_LEDGER)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.details["checked_adapter_results"], 1)

    def test_required_adapter_evidence_fails_when_contract_evidence_is_missing(self) -> None:
        broken_event = {
            **ADAPTER_RESULT_LEDGER[1],
            "details": {
                "adapter": "github.issue",
                "adapter_result": {
                    "status": "planned",
                    "message": "Dry-run planned.",
                    "outputs": {},
                    "evidence": {},
                    "dry_run": True,
                },
            },
        }

        result = eval_required_adapter_evidence([VALID_LEDGER[0], broken_event])

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.details["missing_evidence"][0]["missing"], ["issue_marker"])
        self.assertEqual(result.details["missing_outputs"][0]["missing"], ["github.issue"])

    def test_required_adapter_evidence_blocks_without_sdk_adapter_results(self) -> None:
        result = eval_required_adapter_evidence(VALID_LEDGER)

        self.assertEqual(result.status, "blocked")

    def test_mcp_tool_risk_review_passes_for_low_risk_tool(self) -> None:
        result = eval_mcp_tool_risk_review(MCP_TOOL_LEDGER)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.details["checked_tools"], 1)

    def test_mcp_tool_risk_review_blocks_high_risk_tool(self) -> None:
        risky_event = {
            **MCP_TOOL_LEDGER[1],
            "action_id": "executor.shell_tool",
            "details": {
                "adapter": "mcp.tool",
                "adapter_result": {
                    "status": "planned",
                    "message": "Dry-run planned.",
                    "outputs": {
                        "tool_result": {
                            "server": "local-shell",
                            "tool_name": "run_shell_command",
                            "planned_result_id": "fixture-shell-result",
                        }
                    },
                    "evidence": {
                        "tool_name": "run_shell_command",
                        "tool_result": "fixture-shell-result",
                        "permission_scope": "write_or_execute",
                        "risk_level": "high",
                        "prompt_injection_risk": "medium",
                        "recommended_gate": "approval_required",
                    },
                    "dry_run": True,
                },
            },
        }

        result = eval_mcp_tool_risk_review([VALID_LEDGER[0], risky_event])

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.details["high_risk_tools"][0]["tool_name"], "run_shell_command")

    def test_run_declared_evals_includes_ledger_validity(self) -> None:
        results = run_declared_evals(MANIFEST, VALID_LEDGER)
        ids = [result.id for result in results]

        self.assertEqual(ids[0], "ledger_is_valid")
        self.assertIn("approvals_before_risky_actions", ids)
        self.assertIn("required_adapter_evidence", ids)
        self.assertIn("mcp_tool_risk_review", ids)

    def test_eval_results_become_ledger_events(self) -> None:
        results = run_declared_evals(MANIFEST, VALID_LEDGER)
        events = eval_results_to_events(
            results,
            run_id="run-1",
            start_sequence=2,
            timestamp="2026-07-03T20:01:00+00:00",
        )

        self.assertEqual(events[0].type, "eval.result")
        self.assertEqual(events[0].sequence, 2)
        self.assertEqual(events[0].details["eval_id"], "ledger_is_valid")

    def test_load_jsonl_reads_eval_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.jsonl"
            path.write_text(json.dumps(VALID_LEDGER[0]) + "\n", encoding="utf-8")
            events = load_jsonl(path)

        self.assertEqual(events[0]["run_id"], "run-1")


if __name__ == "__main__":
    unittest.main()
