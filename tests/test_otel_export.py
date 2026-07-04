from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from delegation_bot.otel_export import build_otel_export, render_otel_export, write_otel_export


SAMPLE_EVENTS = [
    {
        "run_id": "dryrun-demo",
        "sequence": 1,
        "timestamp": "2026-07-04T00:00:00+00:00",
        "type": "plan.compiled",
        "status": "planned",
        "message": "Compiled plan.",
        "action_id": None,
        "details": {
            "plan": {
                "id": "demo",
                "mode": "dry-run",
                "objective": "Export a ledger.",
            }
        },
    },
    {
        "run_id": "dryrun-demo",
        "sequence": 2,
        "timestamp": "2026-07-04T00:00:01+00:00",
        "type": "github.issue.planned",
        "status": "planned",
        "message": "Planned issue.",
        "action_id": "executor.issue",
        "details": {
            "adapter": "github.issue",
            "token": "ghp_secret",
            "action": {
                "id": "executor.issue",
                "type": "adapter.github.issue.prepare",
                "risk": "low",
                "requires_approval": False,
                "adapter": "github.issue",
            },
            "adapter_result": {
                "status": "planned",
                "outputs": {"github.issue": {"title": "Demo"}},
                "evidence": {"issue_marker": "delegation-bot:issue:demo"},
                "dry_run": True,
            },
        },
    },
    {
        "run_id": "dryrun-demo",
        "sequence": 3,
        "timestamp": "2026-07-04T00:00:02+00:00",
        "type": "eval.result",
        "status": "passed",
        "message": "Ledger is valid.",
        "action_id": None,
        "details": {"eval_id": "ledger_is_valid"},
    },
]


class OtelExportTests(unittest.TestCase):
    def test_build_otel_export_maps_run_actions_events_and_logs(self) -> None:
        export = build_otel_export(SAMPLE_EVENTS, source="ledger.jsonl")
        data = export.to_dict()
        trace = data["traces"][0]

        self.assertEqual(data["format"], "delegation.otel.trace.v1")
        self.assertEqual(data["resource"]["service.name"], "delegation-bot")
        self.assertEqual(len(trace["spans"]), 2)
        self.assertEqual(trace["spans"][0]["name"], "delegation.run")
        self.assertEqual(trace["spans"][1]["attributes"]["delegation.adapter.id"], "github.issue")
        self.assertEqual(len(data["logs"]), 3)
        self.assertEqual(data["warnings"], [])

    def test_export_redacts_secret_details(self) -> None:
        export = build_otel_export(SAMPLE_EVENTS)
        encoded = json.dumps(export.to_dict(), sort_keys=True)

        self.assertNotIn("ghp_secret", encoded)
        self.assertIn("[redacted]", encoded)

    def test_non_contiguous_sequence_adds_warning(self) -> None:
        events = [dict(event) for event in SAMPLE_EVENTS]
        events[2]["sequence"] = 5

        export = build_otel_export(events)

        self.assertIn("non-contiguous", export.to_dict()["warnings"][0])

    def test_render_and_write_export(self) -> None:
        export = build_otel_export(SAMPLE_EVENTS, source="ledger.jsonl")
        text = render_otel_export(export)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "otel.json"
            write_otel_export(export, path)
            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertIn("OpenTelemetry export", text)
        self.assertEqual(data["traces"][0]["run_id"], "dryrun-demo")


if __name__ == "__main__":
    unittest.main()
