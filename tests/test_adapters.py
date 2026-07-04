from __future__ import annotations

import unittest

from delegation_bot.adapters import get_adapter_contract, list_adapter_contracts, render_adapter_contracts


class AdapterContractTests(unittest.TestCase):
    def test_built_in_contracts_have_required_planning_fields(self) -> None:
        contracts = list_adapter_contracts()
        ids = {contract.id for contract in contracts}

        self.assertIn("codex.thread", ids)
        self.assertIn("github.actions", ids)
        self.assertIn("mcp.tool", ids)
        self.assertIn("openai.agents", ids)
        self.assertIn("anthropic.messages", ids)
        self.assertIn("claude.code", ids)
        self.assertIn("sample.echo", ids)

        for contract in contracts:
            data = contract.to_dict()
            self.assertEqual(data["id"], contract.id)
            self.assertIn(contract.risk, {"low", "medium", "high"})
            self.assertIn(contract.kind, {"workflow", "ai_harness", "model_provider", "tool", "ml_model", "human"})
            self.assertTrue(contract.inputs)
            self.assertTrue(contract.outputs)
            self.assertTrue(contract.planned_event_types)
            self.assertTrue(contract.required_evidence)

    def test_get_adapter_contract_returns_known_contract_or_none(self) -> None:
        contract = get_adapter_contract("codex.thread")

        self.assertIsNotNone(contract)
        self.assertEqual(contract.id if contract else "", "codex.thread")
        self.assertIsNone(get_adapter_contract("unknown.harness"))

    def test_render_adapter_contracts_is_readable(self) -> None:
        text = render_adapter_contracts([get_adapter_contract("mcp.tool")])  # type: ignore[list-item]

        self.assertIn("Adapter contracts", text)
        self.assertIn("mcp.tool", text)
        self.assertIn("outputs:", text)


if __name__ == "__main__":
    unittest.main()
