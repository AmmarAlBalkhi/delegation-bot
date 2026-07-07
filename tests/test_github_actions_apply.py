from __future__ import annotations

import copy
import unittest
from pathlib import Path

from delegation_bot.github_actions_apply import (
    ACTIONS_CONFIRMATION,
    CANCEL_CONFIRMATION,
    FORCE_CANCEL_CONFIRMATION,
    GitHubActionsDispatchResult,
    GitHubActionsDraft,
    GitHubActionsCancelTarget,
    GitHubActionsCancelResult,
    GitHubTokenDiagnostics,
    GitHubWorkflowMetadata,
    GitHubWorkflowRunSummary,
    apply_github_actions_drafts,
    build_actions_cancel_report,
    build_actions_apply_report,
    cancel_github_actions_run,
    render_actions_cancel_report,
    render_actions_apply_report,
)
from delegation_bot.harness_manifest import load_manifest
from delegation_bot.harness_plan import build_dry_run_ledger, compile_plan


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "ai-harness-control-plane.yaml"


def example_manifest_and_ledger() -> tuple[dict, object, list[dict]]:
    manifest = load_manifest(EXAMPLE)
    plan = compile_plan(manifest, source=str(EXAMPLE))
    ledger_events = [event.to_dict() for event in build_dry_run_ledger(plan)]
    return manifest, plan, ledger_events


def renumber(events: list[dict]) -> list[dict]:
    copied = copy.deepcopy(events)
    for sequence, event in enumerate(copied, start=1):
        event["sequence"] = sequence
    return copied


class GitHubActionsApplyTests(unittest.TestCase):
    def test_preview_report_is_ready_for_example_ledger(self) -> None:
        manifest, plan, ledger_events = example_manifest_and_ledger()

        report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
        )
        text = render_actions_apply_report(report)

        self.assertFalse(report.blocked)
        self.assertEqual(report.status, "ready")
        self.assertEqual(len(report.drafts), 1)
        self.assertTrue(report.drafts[0].dispatch_id.startswith("gha-"))
        self.assertIn("actions/runs/dryrun-gha", report.drafts[0].workflow_run_url)
        self.assertIn("GitHub Actions Apply Gate", text)
        self.assertIn("dispatch id: gha-", text)
        self.assertIn("Rerun with `--apply --confirm LIVE_GITHUB_ACTIONS`", text)

    def test_live_dispatch_is_ready_with_confirmation_and_token(self) -> None:
        manifest, plan, ledger_events = example_manifest_and_ledger()

        report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
            apply=True,
            confirmation=ACTIONS_CONFIRMATION,
            token="fake-token",
        )

        self.assertFalse(report.blocked)
        self.assertEqual(report.status, "ready_to_dispatch")
        self.assertTrue(report.live_dispatch_supported)

    def test_dispatch_id_does_not_include_sensitive_input_values(self) -> None:
        first = GitHubActionsDraft(
            action_id="executor.release",
            repository="AmmarAlBalkhi/delegation-bot",
            workflow_ref=".github/workflows/tests.yml",
            ref="main",
            inputs={"mode": "smoke", "api_token": "first-secret"},
        )
        second = GitHubActionsDraft(
            action_id="executor.release",
            repository="AmmarAlBalkhi/delegation-bot",
            workflow_ref=".github/workflows/tests.yml",
            ref="main",
            inputs={"mode": "smoke", "api_token": "second-secret"},
        )

        self.assertEqual(first.dispatch_id, second.dispatch_id)

    def test_cancel_actions_preview_is_ready_without_token(self) -> None:
        report = build_actions_cancel_report("AmmarAlBalkhi/delegation-bot", "123")
        text = render_actions_cancel_report(report)

        self.assertFalse(report.blocked)
        self.assertEqual(report.status, "ready")
        self.assertIn("GitHub Actions Cancel Gate", text)
        self.assertIn("CANCEL_GITHUB_ACTIONS", text)

    def test_cancel_actions_blocks_live_without_confirmation(self) -> None:
        report = build_actions_cancel_report(
            "AmmarAlBalkhi/delegation-bot",
            "123",
            apply=True,
            token="fake-token",
        )

        self.assertTrue(report.blocked)
        self.assertIn("intent.cancel", {gate.id for gate in report.gates if gate.status == "blocked"})

    def test_force_cancel_requires_force_confirmation(self) -> None:
        blocked = build_actions_cancel_report(
            "AmmarAlBalkhi/delegation-bot",
            "123",
            apply=True,
            force=True,
            confirmation=CANCEL_CONFIRMATION,
            token="fake-token",
        )
        ready = build_actions_cancel_report(
            "AmmarAlBalkhi/delegation-bot",
            "123",
            apply=True,
            force=True,
            confirmation=FORCE_CANCEL_CONFIRMATION,
            token="fake-token",
            token_diagnostics=GitHubTokenDiagnostics(available=True, oauth_scopes=("repo",)),
        )

        self.assertTrue(blocked.blocked)
        self.assertFalse(ready.blocked)
        self.assertEqual(ready.status, "ready_to_cancel")

    def test_cancel_actions_writes_ledger_events(self) -> None:
        class FakeClient:
            def cancel_workflow_run(self, target):
                return GitHubActionsCancelResult(
                    status_code=202,
                    api_path="/repos/AmmarAlBalkhi/delegation-bot/actions/runs/123/cancel",
                )

        target = GitHubActionsCancelTarget("AmmarAlBalkhi/delegation-bot", "123")

        events = cancel_github_actions_run(
            target,
            client=FakeClient(),
            run_id="cancel-run",
            start_sequence=1,
            timestamp="2026-07-07T00:00:00+00:00",
        )

        self.assertEqual([event.type for event in events], [
            "github.actions.cancel.started",
            "github.actions.cancel.requested",
            "github.actions.cancel.completed",
        ])
        self.assertEqual(events[1].details["result"]["status_code"], 202)
        self.assertEqual(events[-1].status, "passed")

    def test_live_report_runs_preflight_with_fake_client(self) -> None:
        class FakeClient:
            def get_workflow(self, draft):
                return GitHubWorkflowMetadata(
                    id=123,
                    name="Tests",
                    path=".github/workflows/tests.yml",
                    state="active",
                )

            def active_duplicate_runs(self, draft):
                return ()

        manifest, plan, ledger_events = example_manifest_and_ledger()

        report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
            apply=True,
            confirmation=ACTIONS_CONFIRMATION,
            token="fake-token",
            preflight_client=FakeClient(),
        )

        gate_ids = {gate.id for gate in report.gates}
        self.assertFalse(report.blocked)
        self.assertIn("preflight.workflow_metadata.executor.verification_runner", gate_ids)
        self.assertIn("preflight.duplicate_run.executor.verification_runner", gate_ids)

    def test_live_report_blocks_disabled_workflow_preflight(self) -> None:
        class FakeClient:
            def get_workflow(self, draft):
                return GitHubWorkflowMetadata(
                    id=123,
                    name="Tests",
                    path=".github/workflows/tests.yml",
                    state="disabled_manually",
                )

            def active_duplicate_runs(self, draft):
                return ()

        manifest, plan, ledger_events = example_manifest_and_ledger()

        report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
            apply=True,
            confirmation=ACTIONS_CONFIRMATION,
            token="fake-token",
            preflight_client=FakeClient(),
        )

        self.assertTrue(report.blocked)
        self.assertIn("preflight.workflow_metadata.executor.verification_runner", {
            gate.id for gate in report.gates if gate.status == "blocked"
        })

    def test_live_report_blocks_duplicate_active_workflow_run(self) -> None:
        class FakeClient:
            def get_workflow(self, draft):
                return GitHubWorkflowMetadata(
                    id=123,
                    name="Tests",
                    path=".github/workflows/tests.yml",
                    state="active",
                )

            def active_duplicate_runs(self, draft):
                return (
                    GitHubWorkflowRunSummary(
                        id=456,
                        status="in_progress",
                        event="workflow_dispatch",
                        head_branch="main",
                        html_url="https://github.com/AmmarAlBalkhi/delegation-bot/actions/runs/456",
                    ),
                )

        manifest, plan, ledger_events = example_manifest_and_ledger()

        report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
            apply=True,
            confirmation=ACTIONS_CONFIRMATION,
            token="fake-token",
            preflight_client=FakeClient(),
        )

        self.assertTrue(report.blocked)
        self.assertIn("preflight.duplicate_run.executor.verification_runner", {
            gate.id for gate in report.gates if gate.status == "blocked"
        })

    def test_live_dispatch_writes_ledger_events(self) -> None:
        class FakeClient:
            def get_workflow(self, draft):
                return GitHubWorkflowMetadata(
                    id=123,
                    name="Tests",
                    path=".github/workflows/tests.yml",
                    state="active",
                )

            def active_duplicate_runs(self, draft):
                return ()

            def dispatch_workflow(self, draft):
                return GitHubActionsDispatchResult(
                    workflow_run_id="123",
                    run_url="https://api.github.com/repos/AmmarAlBalkhi/delegation-bot/actions/runs/123",
                    html_url="https://github.com/AmmarAlBalkhi/delegation-bot/actions/runs/123",
                    status_code=200,
                )

        manifest, plan, ledger_events = example_manifest_and_ledger()
        report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
            apply=True,
            confirmation=ACTIONS_CONFIRMATION,
            token="fake-token",
        )

        events = apply_github_actions_drafts(
            report.drafts,
            client=FakeClient(),
            run_id="dryrun-ai-harness-control-plane",
            start_sequence=len(ledger_events) + 1,
            timestamp="2026-07-06T00:00:00+00:00",
        )

        self.assertEqual([event.type for event in events], [
            "github.actions.dispatch.started",
            "github.actions.dispatched",
            "github.actions.dispatch.completed",
        ])
        self.assertEqual(events[1].status, "executed")
        self.assertEqual(events[0].details["dispatch_ids"], [report.drafts[0].dispatch_id])
        self.assertEqual(events[1].details["dispatch_id"], report.drafts[0].dispatch_id)
        self.assertEqual(events[1].details["workflow_run_id"], "123")
        self.assertEqual(
            events[1].details["cancellation"]["cancel_api_path"],
            "/repos/AmmarAlBalkhi/delegation-bot/actions/runs/123/cancel",
        )
        self.assertEqual(events[-1].status, "passed")

    def test_existing_live_dispatch_id_blocks_repeat_dispatch(self) -> None:
        manifest, plan, ledger_events = example_manifest_and_ledger()
        first_report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
        )
        ledger_events.append(
            {
                "run_id": ledger_events[0]["run_id"],
                "sequence": len(ledger_events) + 1,
                "timestamp": "2026-07-07T00:00:00+00:00",
                "type": "github.actions.dispatched",
                "status": "executed",
                "message": "GitHub Actions workflow dispatched.",
                "action_id": first_report.drafts[0].action_id,
                "details": {
                    "adapter": "github.actions",
                    "dispatch_id": first_report.drafts[0].dispatch_id,
                    "repository": first_report.drafts[0].repository,
                    "workflow_ref": first_report.drafts[0].workflow_ref,
                    "ref": first_report.drafts[0].ref,
                },
            }
        )

        repeat_report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
            apply=True,
            confirmation=ACTIONS_CONFIRMATION,
            token="fake-token",
        )

        self.assertTrue(repeat_report.blocked)
        self.assertIn(
            "ledger.dispatch_idempotency",
            {gate.id for gate in repeat_report.gates if gate.status == "blocked"},
        )

    def test_live_dispatch_blocks_when_preflight_changes_after_report(self) -> None:
        class FakeClient:
            def get_workflow(self, draft):
                return GitHubWorkflowMetadata(
                    id=123,
                    name="Tests",
                    path=".github/workflows/tests.yml",
                    state="active",
                )

            def active_duplicate_runs(self, draft):
                return (
                    GitHubWorkflowRunSummary(
                        id=456,
                        status="queued",
                        event="workflow_dispatch",
                        head_branch="main",
                    ),
                )

            def dispatch_workflow(self, draft):  # pragma: no cover - should not be called
                raise AssertionError("dispatch should not run after duplicate preflight")

        manifest, plan, ledger_events = example_manifest_and_ledger()
        report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
            apply=True,
            confirmation=ACTIONS_CONFIRMATION,
            token="fake-token",
        )

        events = apply_github_actions_drafts(
            report.drafts,
            client=FakeClient(),
            run_id="dryrun-ai-harness-control-plane",
            start_sequence=len(ledger_events) + 1,
            timestamp="2026-07-06T00:00:00+00:00",
        )

        self.assertEqual(events[1].type, "github.actions.dispatch.blocked")
        self.assertEqual(events[1].status, "blocked")
        self.assertEqual(events[-1].status, "failed")

    def test_policy_can_require_approval_before_workflow_dispatch(self) -> None:
        manifest, _, ledger_events = example_manifest_and_ledger()
        manifest = copy.deepcopy(manifest)
        manifest["policies"]["approvals"]["required_for"].append("workflow")
        plan = compile_plan(manifest, source=str(EXAMPLE))

        report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
        )

        self.assertTrue(report.blocked)
        self.assertIn("approval.github_actions", {gate.id for gate in report.gates if gate.status == "blocked"})

    def test_approval_evidence_unblocks_workflow_policy_gate(self) -> None:
        manifest, _, _ = example_manifest_and_ledger()
        manifest = copy.deepcopy(manifest)
        manifest["policies"]["approvals"]["required_for"].append("workflow")
        plan = compile_plan(manifest, source=str(EXAMPLE))
        ledger_events = [event.to_dict() for event in build_dry_run_ledger(plan)]
        ledger_events.append(
            {
                "run_id": ledger_events[0]["run_id"],
                "sequence": len(ledger_events) + 1,
                "timestamp": "2026-07-05T10:00:00+00:00",
                "type": "approval.granted",
                "status": "approved",
                "message": "Approved workflow dispatch preview.",
                "action_id": "executor.verification_runner",
                "details": {"approver": "AmmarAlBalkhi", "adapter": "github.actions"},
            }
        )

        report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
        )

        approval_gates = [gate for gate in report.gates if gate.id == "approval.github_actions"]
        self.assertEqual(approval_gates[0].status, "passed")
        self.assertFalse(report.blocked)

    def test_missing_workflow_evidence_blocks_even_when_other_adapter_evidence_exists(self) -> None:
        manifest, plan, ledger_events = example_manifest_and_ledger()
        ledger_events = renumber(
            [
                event
                for event in ledger_events
                if event.get("action_id") != "executor.verification_runner"
            ]
        )

        report = build_actions_apply_report(
            manifest,
            plan,
            ledger_events,
            ledger_source=".delegation/latest.jsonl",
        )

        self.assertTrue(report.blocked)
        self.assertIn("ledger.github_actions_evidence", {gate.id for gate in report.gates if gate.status == "blocked"})


if __name__ == "__main__":
    unittest.main()
