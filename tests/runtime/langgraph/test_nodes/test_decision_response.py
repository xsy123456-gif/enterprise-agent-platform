import unittest

from app.runtime.backends.langgraph.nodes import ResponseNode, ToolDecisionNode


class DecisionResponseNodeTest(unittest.TestCase):
    def test_tool_decision_creates_intent_without_execution(self):
        patch = ToolDecisionNode()({
            "reasoning_output": {
                "action": "tool_call", "tool": "crm_query",
                "arguments": {"customer": "A"},
            }
        })

        self.assertEqual("tool", patch["_action"]["type"])
        self.assertEqual("crm_query", patch["pending_tool_call"]["tool"])

    def test_finish_decision_routes_to_response(self):
        patch = ToolDecisionNode()({
            "reasoning_output": {"action": "finish", "output": "done"}
        })

        self.assertEqual("finish", patch["_action"]["type"])
        self.assertIsNone(patch["tool_call_request"])

    def test_response_node_materializes_output_only(self):
        patch = ResponseNode()({
            "_action": {"type": "finish", "output": "done"},
            "messages": [],
        })

        self.assertEqual("done", patch["response"])
        self.assertEqual("completed", patch["status"])
        self.assertEqual("assistant", patch["messages"][-1]["role"])
