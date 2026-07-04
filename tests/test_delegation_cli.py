from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from delegation_bot.cli import main


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


if __name__ == "__main__":
    unittest.main()
