from __future__ import annotations

import unittest
from pathlib import Path

from delegation_bot.eval_feedback import build_feedback_issue_drafts, build_feedback_resolution_drafts, render_feedback_report
from delegation_bot.evals import (
    eval_ledger_is_valid,
    eval_mcp_tool_risk_review,
    eval_no_duplicate_issue_markers,
    eval_required_adapter_evidence,
)
from delegation_bot.ledger import LedgerFilter, build_ledger_view, load_ledger_events, render_ledger_view


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "ledgers"


class LedgerFixtureTests(unittest.TestCase):
    def test_good_adapter_fixture_passes_required_evidence_eval(self) -> None:
        events = load_ledger_events(FIXTURES / "adapter-good.jsonl")

        self.assertEqual(eval_ledger_is_valid(events).status, "passed")
        self.assertEqual(eval_required_adapter_evidence(events).status, "passed")

    def test_blocked_adapter_fixture_blocks_required_evidence_eval(self) -> None:
        events = load_ledger_events(FIXTURES / "adapter-blocked.jsonl")
        result = eval_required_adapter_evidence(events)

        self.assertEqual(eval_ledger_is_valid(events).status, "passed")
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.details["blocked_results"][0]["adapter"], "sample.echo")

    def test_failed_adapter_fixture_fails_required_evidence_eval(self) -> None:
        events = load_ledger_events(FIXTURES / "adapter-failed.jsonl")
        result = eval_required_adapter_evidence(events)

        self.assertEqual(eval_ledger_is_valid(events).status, "passed")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.details["failed_results"][0]["adapter"], "sample.echo")

    def test_fixture_ledger_views_are_readable_and_filterable(self) -> None:
        events = load_ledger_events(FIXTURES / "adapter-good.jsonl")
        view = build_ledger_view(events, ledger_filter=LedgerFilter(adapter="sample.echo"))
        text = render_ledger_view(view)

        self.assertEqual(view.total_events, 4)
        self.assertEqual(len(view.adapter_evidence), 2)
        self.assertIn("sample.echo", text)
        self.assertIn("echo_hash=fixture-good-echo", text)

    def test_applied_github_issue_fixture_is_readable_and_not_duplicate(self) -> None:
        events = load_ledger_events(FIXTURES / "github-issue-applied.jsonl")
        view = build_ledger_view(events, ledger_filter=LedgerFilter(adapter="github.issue"))
        text = render_ledger_view(view)

        self.assertEqual(eval_ledger_is_valid(events).status, "passed")
        self.assertEqual(eval_no_duplicate_issue_markers(events).status, "passed")
        self.assertEqual(view.total_events, 6)
        self.assertIn("github.issue.created", text)
        self.assertIn("issue_number=123", text)

    def test_github_actions_preview_fixture_has_run_url_evidence(self) -> None:
        events = load_ledger_events(FIXTURES / "github-actions-preview.jsonl")
        view = build_ledger_view(events, ledger_filter=LedgerFilter(adapter="github.actions"))
        text = render_ledger_view(view)

        self.assertEqual(eval_ledger_is_valid(events).status, "passed")
        self.assertEqual(eval_required_adapter_evidence(events).status, "passed")
        self.assertEqual(view.total_events, 5)
        self.assertIn("github.actions.planned", text)
        self.assertIn("workflow_run_url=https://github.com/AmmarAlBalkhi/delegation-bot/actions/runs/dryrun-gha-fixture-preview", text)

    def test_mcp_tool_risk_fixture_blocks_mcp_risk_review(self) -> None:
        events = load_ledger_events(FIXTURES / "mcp-tool-risk.jsonl")
        view = build_ledger_view(events, ledger_filter=LedgerFilter(adapter="mcp.tool"))
        text = render_ledger_view(view)

        self.assertEqual(eval_ledger_is_valid(events).status, "passed")
        self.assertEqual(eval_required_adapter_evidence(events).status, "passed")
        self.assertEqual(eval_mcp_tool_risk_review(events).status, "blocked")
        self.assertEqual(view.total_events, 4)
        self.assertIn("risk_level=high", text)
        self.assertIn("prompt_injection_risk=high", text)

    def test_feedback_issue_memory_fixture_reuses_live_issue_link(self) -> None:
        events = load_ledger_events(FIXTURES / "feedback-issue-memory.jsonl")
        manifest = {
            "id": "feedback-memory-fixture",
            "policies": {"permissions": {"allowed_repositories": ["AmmarAlBalkhi/delegation-bot"]}},
        }
        view = build_ledger_view(events, ledger_filter=LedgerFilter(adapter="github.issue"))
        text = render_ledger_view(view)

        drafts = build_feedback_issue_drafts(
            manifest,
            events,
            repository="AmmarAlBalkhi/delegation-bot",
            ledger_source="examples/ledgers/feedback-issue-memory.jsonl",
        )
        report = render_feedback_report(drafts)

        self.assertEqual(eval_ledger_is_valid(events).status, "passed")
        self.assertEqual(eval_no_duplicate_issue_markers(events).status, "passed")
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].operation, "update")
        self.assertEqual(drafts[0].live_issue_number, 321)
        self.assertIn("live_issue_number=321", text)
        self.assertIn("live issue: `#321` https://github.com/AmmarAlBalkhi/delegation-bot/issues/321", report)

    def test_feedback_recovery_fixture_is_readable_and_not_duplicate(self) -> None:
        events = load_ledger_events(FIXTURES / "feedback-recovery.jsonl")
        view = build_ledger_view(events, ledger_filter=LedgerFilter(adapter="github.issue"))
        text = render_ledger_view(view)

        self.assertEqual(eval_ledger_is_valid(events).status, "passed")
        self.assertEqual(eval_no_duplicate_issue_markers(events).status, "passed")
        self.assertEqual(view.total_events, 8)
        self.assertIn("feedback.resolve.required_adapter_evidence", text)
        self.assertIn("live_issue_number=321", text)

    def test_feedback_recovery_ready_fixture_drafts_resolution(self) -> None:
        events = load_ledger_events(FIXTURES / "feedback-recovery-ready.jsonl")
        manifest = {
            "id": "feedback-memory-fixture",
            "policies": {"permissions": {"allowed_repositories": ["AmmarAlBalkhi/delegation-bot"]}},
        }

        drafts = build_feedback_resolution_drafts(
            manifest,
            events,
            repository="AmmarAlBalkhi/delegation-bot",
            ledger_source="examples/ledgers/feedback-recovery-ready.jsonl",
        )

        self.assertEqual(eval_ledger_is_valid(events).status, "passed")
        self.assertEqual(eval_no_duplicate_issue_markers(events).status, "passed")
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].operation, "resolve")
        self.assertEqual(drafts[0].live_issue_number, 321)


if __name__ == "__main__":
    unittest.main()
