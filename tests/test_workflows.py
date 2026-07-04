from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def test_delegation_workflow_uploads_run_evidence_artifact(self) -> None:
        workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "delegation.yml").read_text(encoding="utf-8"))
        steps = workflow["jobs"]["run"]["steps"]

        names = [step.get("name") for step in steps]
        upload_step = next(step for step in steps if step.get("name") == "Upload run evidence")

        self.assertIn("Generate Harnessfile dry-run evidence", names)
        self.assertIn("Generate adapter fixture artifacts", names)
        self.assertIn("Collect release artifact manifest", names)
        self.assertEqual(upload_step["uses"], "actions/upload-artifact@v7")
        self.assertEqual(upload_step["with"]["name"], "delegation-run-evidence")
        self.assertIn(".delegation/*.jsonl", upload_step["with"]["path"])
        self.assertIn(".delegation/fixtures/*.jsonl", upload_step["with"]["path"])
        self.assertIn("LICENSE", upload_step["with"]["path"])
        self.assertIn("NOTICE", upload_step["with"]["path"])
        self.assertEqual(upload_step["with"]["if-no-files-found"], "error")

    def test_tests_workflow_uploads_qa_evidence_artifact(self) -> None:
        workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8"))
        steps = workflow["jobs"]["python"]["steps"]

        upload_step = next(step for step in steps if step.get("name") == "Upload QA evidence")

        self.assertEqual(upload_step["uses"], "actions/upload-artifact@v7")
        self.assertEqual(upload_step["with"]["name"], "delegation-qa-evidence")
        self.assertIn(".delegation/*.jsonl", upload_step["with"]["path"])
        self.assertIn(".delegation/*.log", upload_step["with"]["path"])
        self.assertIn("LICENSE", upload_step["with"]["path"])
        self.assertIn("NOTICE", upload_step["with"]["path"])


if __name__ == "__main__":
    unittest.main()
