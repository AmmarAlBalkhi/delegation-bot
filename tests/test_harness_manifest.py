from __future__ import annotations

import unittest

from delegation_bot.harness_manifest import summarize_manifest, validate_manifest


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
        }
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
        }
    ],
    "executors": [
        {"id": "planner", "kind": "workflow", "adapter": "github.issue"},
        {"id": "agent", "kind": "ai_harness", "adapter": "codex.thread", "model": "planner_model"},
    ],
    "outputs": ["github.issue", {"type": "run_ledger"}],
    "evals": [{"id": "tests_pass", "type": "quality_gate"}],
}


class HarnessManifestTests(unittest.TestCase):
    def test_valid_manifest_has_no_errors(self) -> None:
        self.assertEqual(validate_manifest(VALID_MANIFEST), [])

    def test_requires_core_fields(self) -> None:
        errors = validate_manifest({})

        self.assertIn("`version` must be delegation.ai/v1", errors)
        self.assertIn("`id` must be a non-empty string", errors)
        self.assertIn("`objective` must be a non-empty string", errors)
        self.assertIn("`triggers` must be a non-empty list", errors)
        self.assertIn("`executors` must be a non-empty list", errors)
        self.assertIn("`outputs` must be a non-empty list", errors)

    def test_rejects_duplicate_executor_ids(self) -> None:
        manifest = dict(VALID_MANIFEST)
        manifest["executors"] = [
            {"id": "agent", "kind": "ai_harness", "adapter": "codex.thread"},
            {"id": "agent", "kind": "workflow", "adapter": "github.actions"},
        ]

        self.assertIn("duplicate executor id `agent`", validate_manifest(manifest))

    def test_rejects_unknown_model_reference(self) -> None:
        manifest = dict(VALID_MANIFEST)
        manifest["executors"] = [
            {"id": "agent", "kind": "ai_harness", "adapter": "codex.thread", "model": "missing"}
        ]

        self.assertIn(
            "`executors[0].model` references unknown model `missing`",
            validate_manifest(manifest),
        )

    def test_rejects_unknown_agent_capability_pack_reference(self) -> None:
        manifest = dict(VALID_MANIFEST)
        manifest["agents"] = [
            {
                "id": "planner",
                "runtime": "openai.agents",
                "autonomy_level": "draft",
                "capability_packs": ["missing"],
            }
        ]

        self.assertIn(
            "`agents[0].capability_packs` references unknown pack `missing`",
            validate_manifest(manifest),
        )

    def test_rejects_unknown_autonomy_level(self) -> None:
        manifest = dict(VALID_MANIFEST)
        manifest["agents"] = [
            {"id": "planner", "runtime": "openai.agents", "autonomy_level": "magic"}
        ]

        errors = validate_manifest(manifest)

        self.assertTrue(
            any("`agents[0].autonomy_level` must be one of" in error for error in errors),
            errors,
        )

    def test_rejects_invalid_mcp_allowlist_policy_shape(self) -> None:
        manifest = dict(VALID_MANIFEST)
        manifest["policies"] = {
            "permissions": {
                "allowed_mcp_servers": "local",
                "allowed_mcp_tools": ["inspect_repository", ""],
            }
        }

        errors = validate_manifest(manifest)

        self.assertIn("`policies.permissions.allowed_mcp_servers` must be a list when provided", errors)
        self.assertIn("`policies.permissions.allowed_mcp_tools[1]` must be a non-empty string", errors)

    def test_summary_names_adapters_and_outputs(self) -> None:
        summary = summarize_manifest(VALID_MANIFEST)

        self.assertIn("Harnessfile: ai-harness-control-plane", summary)
        self.assertIn("Agents: 1", summary)
        self.assertIn("Capability packs: 1", summary)
        self.assertIn("Models: 1", summary)
        self.assertIn("codex.thread", summary)
        self.assertIn("github.issue", summary)
        self.assertIn("run_ledger", summary)


if __name__ == "__main__":
    unittest.main()
