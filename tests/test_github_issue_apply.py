from __future__ import annotations

import copy
import unittest
from pathlib import Path

from delegation_bot.github_issue_apply import (
    APPLY_CONFIRMATION,
    FEEDBACK_CLOSE_CONFIRMATION,
    FEEDBACK_CONFIRMATION,
    apply_feedback_resolution_drafts,
    apply_github_issue_drafts,
    build_apply_report,
    build_feedback_apply_report,
)
from delegation_bot.harness_manifest import load_manifest
from delegation_bot.harness_plan import build_dry_run_ledger, compile_plan
from delegation_bot.ledger import load_ledger_events


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "ai-harness-control-plane.yaml"


class FakeIssueClient:
    def __init__(self, existing: dict | None = None) -> None:
        self.existing = existing
        self.created: list[dict] = []
        self.updated: list[dict] = []
        self.comments: list[dict] = []
        self.closed: list[dict] = []

    def find_issue_by_marker(self, repository: str, marker: str) -> dict | None:
        return self.existing

    def create_issue(self, repository: str, title: str, body: str) -> dict:
        issue = {
            "number": 7,
            "html_url": f"https://github.com/{repository}/issues/7",
            "title": title,
            "body": body,
        }
        self.created.append(issue)
        return issue

    def update_issue(self, repository: str, number: int, title: str, body: str) -> dict:
        issue = {
            "number": number,
            "html_url": f"https://github.com/{repository}/issues/{number}",
            "title": title,
            "body": body,
        }
        self.updated.append(issue)
        return issue

    def create_comment(self, repository: str, number: int, body: str) -> dict:
        comment = {
            "id": 99,
            "html_url": f"https://github.com/{repository}/issues/{number}#issuecomment-99",
            "body": body,
        }
        self.comments.append(comment)
        return comment

    def close_issue(self, repository: str, number: int) -> dict:
        issue = {
            "number": number,
            "html_url": f"https://github.com/{repository}/issues/{number}",
            "state": "closed",
        }
        self.closed.append(issue)
        return issue


def example_manifest_and_ledger() -> tuple[dict, object, list[dict]]:
    manifest = load_manifest(EXAMPLE)
    plan = compile_plan(manifest, source=str(EXAMPLE))
    ledger_events = [event.to_dict() for event in build_dry_run_ledger(plan)]
    return manifest, plan, ledger_events


def feedback_recovery_manifest_and_ledger() -> tuple[dict, list[dict]]:
    events = load_ledger_events(ROOT / "examples" / "ledgers" / "feedback-recovery-ready.jsonl")
    manifest = {
        "id": "feedback-memory-fixture",
        "policies": {"permissions": {"allowed_repositories": ["AmmarAlBalkhi/delegation-bot"]}},
    }
    return manifest, events


class GitHubIssueApplyTests(unittest.TestCase):
    def test_preview_report_is_ready_for_example_ledger(self) -> None:
        manifest, plan, ledger_events = example_manifest_and_ledger()

        report = build_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
        )

        self.assertFalse(report.blocked)
        self.assertEqual(report.status, "ready")
        self.assertEqual(len(report.drafts), 1)
        self.assertIn("delegation-bot:", report.drafts[0].body)
        self.assertIn("source ledger: `.delegation/latest.jsonl`", report.drafts[0].body)

    def test_live_apply_requires_confirmation_and_token(self) -> None:
        manifest, plan, ledger_events = example_manifest_and_ledger()

        report = build_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
            apply=True,
            confirmation=None,
            token=None,
        )

        blocked_gate_ids = {gate.id for gate in report.gates if gate.status == "blocked"}
        self.assertTrue(report.blocked)
        self.assertIn("intent.apply", blocked_gate_ids)
        self.assertIn("github.token", blocked_gate_ids)

    def test_policy_can_require_approval_before_issue_apply(self) -> None:
        manifest, plan, ledger_events = example_manifest_and_ledger()
        manifest = copy.deepcopy(manifest)
        manifest["policies"]["approvals"]["required_for"].append("github_issue")

        report = build_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
        )

        self.assertTrue(report.blocked)
        self.assertIn("approval.github_issue", {gate.id for gate in report.gates if gate.status == "blocked"})

    def test_apply_drafts_create_issue_events_with_fake_client(self) -> None:
        manifest, plan, ledger_events = example_manifest_and_ledger()
        report = build_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
            apply=True,
            confirmation=APPLY_CONFIRMATION,
            token="fake-token",
        )

        events = apply_github_issue_drafts(
            report.drafts,
            client=FakeIssueClient(),
            run_id="run-1",
            start_sequence=len(ledger_events) + 1,
            timestamp="2026-07-04T12:00:00+00:00",
        )

        event_types = [event.type for event in events]
        self.assertIn("github.issue.apply.started", event_types)
        self.assertIn("github.issue.created", event_types)
        self.assertIn("github.issue.apply.completed", event_types)
        self.assertEqual(events[-1].status, "succeeded")

    def test_apply_drafts_update_existing_marker_with_fake_client(self) -> None:
        manifest, plan, ledger_events = example_manifest_and_ledger()
        report = build_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
            apply=True,
            confirmation=APPLY_CONFIRMATION,
            token="fake-token",
        )
        existing = {"number": 3, "body": f"existing {report.drafts[0].marker}"}
        client = FakeIssueClient(existing=existing)

        events = apply_github_issue_drafts(
            report.drafts,
            client=client,
            run_id="run-1",
            start_sequence=len(ledger_events) + 1,
            timestamp="2026-07-04T12:00:00+00:00",
        )

        self.assertTrue(client.updated)
        self.assertIn("github.issue.updated", [event.type for event in events])
        self.assertEqual(events[1].details["issue_number"], 3)

    def test_feedback_apply_preview_targets_existing_live_issue(self) -> None:
        manifest, ledger_events = feedback_recovery_manifest_and_ledger()

        report = build_feedback_apply_report(
            manifest,
            ledger_events,
            ledger_source="examples/ledgers/feedback-recovery.jsonl",
        )

        self.assertFalse(report.blocked)
        self.assertEqual(report.status, "ready")
        self.assertEqual(len(report.drafts), 1)
        self.assertEqual(report.drafts[0].live_issue_number, 321)

    def test_feedback_apply_live_comment_requires_exact_confirmation(self) -> None:
        manifest, ledger_events = feedback_recovery_manifest_and_ledger()

        report = build_feedback_apply_report(
            manifest,
            ledger_events,
            ledger_source="examples/ledgers/feedback-recovery.jsonl",
            apply=True,
            close=False,
            confirmation=FEEDBACK_CLOSE_CONFIRMATION,
            token="fake-token",
        )

        blocked_gate_ids = {gate.id for gate in report.gates if gate.status == "blocked"}
        self.assertTrue(report.blocked)
        self.assertIn("intent.apply", blocked_gate_ids)

    def test_feedback_apply_close_requires_stronger_confirmation(self) -> None:
        manifest, ledger_events = feedback_recovery_manifest_and_ledger()

        report = build_feedback_apply_report(
            manifest,
            ledger_events,
            ledger_source="examples/ledgers/feedback-recovery.jsonl",
            apply=True,
            close=True,
            confirmation=FEEDBACK_CONFIRMATION,
            token="fake-token",
        )

        blocked_gate_ids = {gate.id for gate in report.gates if gate.status == "blocked"}
        self.assertTrue(report.blocked)
        self.assertIn("intent.apply", blocked_gate_ids)

    def test_feedback_apply_drafts_create_comment_and_close_events(self) -> None:
        manifest, ledger_events = feedback_recovery_manifest_and_ledger()
        report = build_feedback_apply_report(
            manifest,
            ledger_events,
            ledger_source="examples/ledgers/feedback-recovery.jsonl",
            apply=True,
            close=True,
            confirmation=FEEDBACK_CLOSE_CONFIRMATION,
            token="fake-token",
        )
        client = FakeIssueClient()

        events = apply_feedback_resolution_drafts(
            report.drafts,
            client=client,
            run_id="run-1",
            start_sequence=len(ledger_events) + 1,
            close=True,
            timestamp="2026-07-05T12:00:00+00:00",
        )

        self.assertTrue(client.comments)
        self.assertTrue(client.closed)
        event_types = [event.type for event in events]
        self.assertIn("github.issue.feedback_apply.started", event_types)
        self.assertIn("github.issue.comment.created", event_types)
        self.assertIn("github.issue.closed", event_types)
        self.assertIn("github.issue.feedback_apply.completed", event_types)
        self.assertEqual(events[-1].status, "succeeded")
        self.assertEqual(events[1].details["comment_url"], "https://github.com/AmmarAlBalkhi/delegation-bot/issues/321#issuecomment-99")
        self.assertEqual(events[2].details["feedback"]["operation"], "close")

        combined_events = [*ledger_events, *[event.to_dict() for event in events]]
        followup = build_feedback_apply_report(
            manifest,
            combined_events,
            ledger_source="examples/ledgers/feedback-recovery-ready.jsonl",
        )
        self.assertEqual(followup.status, "no_action")
        self.assertEqual(len(followup.drafts), 0)


if __name__ == "__main__":
    unittest.main()
