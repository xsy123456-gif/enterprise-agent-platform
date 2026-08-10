import unittest

from app.runtime.backends.langgraph.nodes import ContextNode, ReasoningNode


class ContextReasoningNodeTest(unittest.TestCase):
    def test_nodes_initialize(self):
        self.assertIsInstance(ContextNode(), ContextNode)
        self.assertIsInstance(ReasoningNode(), ReasoningNode)

    def test_context_node_builds_messages_from_input(self):
        patch = ContextNode()({"input": "analyze", "metadata": {}})

        self.assertEqual(
            [{"role": "user", "content": "analyze"}], patch["messages"]
        )
        self.assertEqual("running", patch["status"])

    def test_reasoning_node_invokes_injected_reasoner(self):
        calls = []

        def reasoner(messages):
            calls.append(messages)
            return {"action": "finish", "output": "done"}

        patch = ReasoningNode(reasoner)({
            "messages": [{"role": "user", "content": "task"}],
        })

        self.assertEqual(1, len(calls))
        self.assertEqual("done", patch["reasoning_output"]["output"])
