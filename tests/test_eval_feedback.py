from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from delegation_bot.eval_feedback import (
    build_feedback_issue_drafts,
    build_feedback_issue_drafts_from_results,
    eval_result_to_event,
    feedback_drafts_to_events,
    render_feedback_report,
    sanitize_details,
)
from delegation_bot.evals import EvalResult, eval_ledger_is_valid


MANIFEST = {
    "id": "feedback-test",
    "policies": {"permissions": {"allowed_repositories": ["AmmarAlBalkhi/delegation-bot"]}},
}


BASE_EVENT = {
    "run_id": "run-1",
    "sequence": 1,
    "timestamp": "2026-07-04T08:00:00+00:00",
    "type": "eval.result",
    "status": "failed",
    "message": "Adapter results are missing required contract evidence or outputs.",
    "action_id": None,
    "details": {
        "eval_id": "required_adapter_evidence",
        "eval": {
            "id": "required_adapter_evidence",
            "status": "failed",
            "message": "Adapter evidence missing.",
            "details": {
                "missing_evidence": [{"adapter": "demo.adapter", "missing": ["proof"]}],
                "api_token": "secret-value",
            },
        },
    },
}


class EvalFeedbackTests(unittest.TestCase):
    def test_failed_eval_result_becomes_dry_run_issue_draft(self) -> None:
        drafts = build_feedback_issue_drafts(MANIFEST, [BASE_EVENT], ledger_source="ledger.jsonl")

        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].eval_id, "required_adapter_evidence")
        self.assertIn("<!-- delegation-bot:eval:required_adapter_evidence:", drafts[0].body)
        self.assertIn("[redacted]", drafts[0].body)
        self.assertNotIn("secret-value", drafts[0].body)
        self.assertEqual(drafts[0].adapter_result.status, "planned")
        self.assertIn("github.issue", drafts[0].adapter_result.outputs)
        self.assertEqual(drafts[0].adapter_result.evidence["issue_marker"], drafts[0].marker)
        self.assertEqual(drafts[0].adapter_result.outputs["github.issue"]["issue_marker"], drafts[0].marker)
        self.assertEqual(drafts[0].operation, "create")
        self.assertEqual(drafts[0].occurrence_count, 1)

    def test_blocked_eval_requires_explicit_flag(self) -> None:
        blocked = {**BASE_EVENT, "status": "blocked"}
        blocked["details"] = {
            **BASE_EVENT["details"],
            "eval": {**BASE_EVENT["details"]["eval"], "status": "blocked"},
        }

        self.assertEqual(build_feedback_issue_drafts(MANIFEST, [blocked]), [])
        self.assertEqual(build_feedback_issue_drafts(MANIFEST, [blocked], include_blocked=True), [])
        self.assertEqual(
            len(
                build_feedback_issue_drafts(
                    MANIFEST,
                    [blocked],
                    include_blocked=True,
                    blocked_repeat_threshold=1,
                )
            ),
            1,
        )

    def test_repeated_blocked_eval_crosses_repeat_threshold(self) -> None:
        first = copy.deepcopy(BASE_EVENT)
        first["status"] = "blocked"
        first["details"]["eval"]["status"] = "blocked"
        second = copy.deepcopy(first)
        second["sequence"] = 2

        drafts = build_feedback_issue_drafts(
            MANIFEST,
            [first, second],
            ledger_source="ledger.jsonl",
            include_blocked=True,
        )

        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].operation, "update")
        self.assertEqual(drafts[0].occurrence_count, 2)
        self.assertEqual(drafts[0].title, "Update eval blocked: required_adapter_evidence")

    def test_repeated_eval_results_are_grouped_into_one_update_draft(self) -> None:
        repeated = copy.deepcopy(BASE_EVENT)
        repeated["sequence"] = 2

        drafts = build_feedback_issue_drafts(MANIFEST, [BASE_EVENT, repeated], ledger_source="ledger.jsonl")

        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].operation, "update")
        self.assertEqual(drafts[0].occurrence_count, 2)
        self.assertIn("matching eval occurrences in this ledger: `2`", drafts[0].body)
        self.assertTrue(drafts[0].adapter_result.action_id.startswith("feedback.update."))

    def test_existing_feedback_marker_turns_later_draft_into_update(self) -> None:
        first_draft = build_feedback_issue_drafts(MANIFEST, [BASE_EVENT], ledger_source="ledger.jsonl")[0]
        existing_feedback_event = {
            "run_id": "run-1",
            "sequence": 2,
            "timestamp": "2026-07-04T08:01:00+00:00",
            "type": "github.issue.planned",
            "status": "planned",
            "message": "Feedback issue planned.",
            "action_id": first_draft.adapter_result.action_id,
            "details": {"feedback": {"marker": first_draft.marker}},
        }

        drafts = build_feedback_issue_drafts(
            MANIFEST,
            [BASE_EVENT, existing_feedback_event],
            ledger_source="ledger.jsonl",
        )

        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].operation, "update")
        self.assertEqual(drafts[0].existing_feedback_events, 1)
        self.assertIn("existing feedback events in this ledger: `1`", drafts[0].body)

    def test_live_feedback_issue_memory_turns_later_draft_into_update(self) -> None:
        first_draft = build_feedback_issue_drafts(MANIFEST, [BASE_EVENT], ledger_source="ledger.jsonl")[0]
        applied_event = {
            "run_id": "run-1",
            "sequence": 2,
            "timestamp": "2026-07-04T08:02:00+00:00",
            "type": "github.issue.created",
            "status": "executed",
            "message": "GitHub Issue created.",
            "action_id": first_draft.adapter_result.action_id,
            "details": {
                "adapter": "github.issue",
                "repository": "AmmarAlBalkhi/delegation-bot",
                "issue_marker": first_draft.marker,
                "issue_number": 17,
                "issue_url": "https://github.com/AmmarAlBalkhi/delegation-bot/issues/17",
            },
        }

        drafts = build_feedback_issue_drafts(
            MANIFEST,
            [BASE_EVENT, applied_event],
            ledger_source="ledger.jsonl",
        )
        events = feedback_drafts_to_events(
            drafts,
            run_id="run-1",
            start_sequence=3,
            timestamp="2026-07-04T08:03:00+00:00",
        )
        feedback_details = events[0].details["feedback"]
        report = render_feedback_report(drafts)

        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].operation, "update")
        self.assertEqual(drafts[0].existing_live_issue_events, 1)
        self.assertEqual(drafts[0].live_issue_number, 17)
        self.assertEqual(drafts[0].live_issue_url, "https://github.com/AmmarAlBalkhi/delegation-bot/issues/17")
        self.assertIn("existing live issue events in this ledger: `1`", drafts[0].body)
        self.assertIn("live GitHub issue: `#17` https://github.com/AmmarAlBalkhi/delegation-bot/issues/17", drafts[0].body)
        self.assertEqual(feedback_details["live_issue_number"], 17)
        self.assertEqual(feedback_details["live_issue_url"], "https://github.com/AmmarAlBalkhi/delegation-bot/issues/17")
        self.assertIn("live issue: `#17` https://github.com/AmmarAlBalkhi/delegation-bot/issues/17", report)

    def test_feedback_drafts_can_be_appended_as_valid_ledger_events(self) -> None:
        drafts = build_feedback_issue_drafts(MANIFEST, [BASE_EVENT], ledger_source="ledger.jsonl")
        events = feedback_drafts_to_events(
            drafts,
            run_id="run-1",
            start_sequence=2,
            timestamp="2026-07-04T08:01:00+00:00",
        )
        ledger = [
            {
                "run_id": "run-1",
                "sequence": 1,
                "timestamp": "2026-07-04T08:00:00+00:00",
                "type": "plan.compiled",
                "status": "planned",
                "message": "Compiled.",
                "action_id": None,
                "details": {},
            },
            *[event.to_dict() for event in events],
        ]

        self.assertEqual(eval_ledger_is_valid(ledger).status, "passed")
        self.assertTrue(any(event.type == "github.issue.planned" for event in events))

    def test_feedback_report_is_readable(self) -> None:
        drafts = build_feedback_issue_drafts(MANIFEST, [BASE_EVENT], ledger_source="ledger.jsonl")
        report = render_feedback_report(drafts)

        self.assertIn("Feedback issue drafts", report)
        self.assertIn("Eval failed: required_adapter_evidence", report)

    def test_eval_result_to_event_matches_feedback_event_shape(self) -> None:
        result = EvalResult(
            "required_adapter_evidence",
            "failed",
            "Adapter evidence missing.",
            {"api_token": "secret-value"},
        )

        event = eval_result_to_event(
            result,
            run_id="run-1",
            sequence=3,
            timestamp="2026-07-04T08:00:00+00:00",
        )

        self.assertEqual(event["type"], "eval.result")
        self.assertEqual(event["details"]["eval_id"], "required_adapter_evidence")
        self.assertEqual(event["details"]["eval"]["details"]["api_token"], "secret-value")

    def test_eval_results_become_feedback_drafts_without_written_eval_events(self) -> None:
        result = EvalResult(
            "required_adapter_evidence",
            "failed",
            "Adapter evidence missing.",
            {"api_token": "secret-value"},
        )

        drafts = build_feedback_issue_drafts_from_results(
            MANIFEST,
            [result],
            ledger_events=[],
            ledger_source="ledger.jsonl",
            run_id="run-1",
            timestamp="2026-07-04T08:00:00+00:00",
        )

        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].eval_id, "required_adapter_evidence")
        self.assertEqual(drafts[0].operation, "create")
        self.assertIn("[redacted]", drafts[0].body)
        self.assertNotIn("secret-value", drafts[0].body)

    def test_direct_blocked_eval_can_use_history_for_update_threshold(self) -> None:
        blocked_result = EvalResult("tests_pass_before_pr", "blocked", "No pull request evidence.", {})
        prior_blocked = {
            "run_id": "run-1",
            "sequence": 3,
            "timestamp": "2026-07-04T08:00:00+00:00",
            "type": "eval.result",
            "status": "blocked",
            "message": "No pull request evidence.",
            "action_id": None,
            "details": {"eval_id": "tests_pass_before_pr", "eval": blocked_result.to_dict()},
        }

        drafts = build_feedback_issue_drafts_from_results(
            MANIFEST,
            [blocked_result],
            ledger_events=[prior_blocked],
            include_blocked=True,
            blocked_repeat_threshold=2,
            ledger_source="ledger.jsonl",
        )

        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].operation, "update")
        self.assertEqual(drafts[0].occurrence_count, 2)

    def test_sanitize_details_redacts_nested_secret_keys(self) -> None:
        details = {"nested": [{"password": "abc"}, {"safe": "ok"}]}

        self.assertEqual(sanitize_details(details), {"nested": [{"password": "[redacted]"}, {"safe": "ok"}]})


if __name__ == "__main__":
    unittest.main()
