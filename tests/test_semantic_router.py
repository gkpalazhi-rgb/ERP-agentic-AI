import unittest
from unittest.mock import patch

from app.services.semantic_router import IntentChainOrchestrator, IntentResolver


class SemanticRouterTests(unittest.TestCase):
    def setUp(self):
        model_patcher = patch("app.services.semantic_router._get_model", return_value=None)
        self.addCleanup(model_patcher.stop)
        model_patcher.start()
        self.resolver = IntentResolver()
        self.orchestrator = IntentChainOrchestrator()

    def test_single_intent_resolution(self):
        result = self.resolver.resolve("check inventory for cement")
        self.assertEqual(result["intents"][0]["intent"], "inventory_query")

    def test_multi_intent_resolution(self):
        result = self.resolver.resolve("verify po-1002 and update inventory for cement 10 units")
        intents = [x["intent"] for x in result["intents"]]
        self.assertIn("purchase_order_verify", intents)
        self.assertIn("inventory_update", intents)
        self.assertTrue(result["is_multi_intent"])
        self.assertEqual(result["entities"]["po_number"], "PO-1002")

    def test_unknown_intent_resolution(self):
        result = self.resolver.resolve("tell me a bedtime story")
        self.assertEqual(result["intents"][0]["intent"], "unknown_intent")

    def test_chain_detection(self):
        resolved = {
            "intents": [
                {"intent": "purchase_order_create", "confidence": 0.82},
                {"intent": "purchase_invoice_create", "confidence": 0.78},
            ],
            "entities": {"item_name": "cement", "quantity": 20, "po_number": None},
            "is_multi_intent": True,
            "raw_input": "create po and invoice",
        }
        with_chain = self.orchestrator.attach_chain(resolved)
        self.assertIn("chain", with_chain)
        self.assertEqual(with_chain["chain"]["name"], "order_and_invoice")

    def test_chain_execution_passes_context(self):
        def verify_tool(entities):
            return {"success": True, "verified_items": [entities.get("item_name", "cement")], "quantity": 10}

        def update_tool(entities):
            return {"success": True, "updated_items": entities.get("verified_items", [])}

        report = self.orchestrator.execute_chain(
            "verify_and_update",
            {"item_name": "cement", "po_number": "PO-1002"},
            {
                "purchase_order_verify": verify_tool,
                "inventory_update": update_tool,
            },
        )
        self.assertEqual(report["final_status"], "success")
        self.assertEqual(report["steps_completed"], ["purchase_order_verify", "inventory_update"])


if __name__ == "__main__":
    unittest.main()
