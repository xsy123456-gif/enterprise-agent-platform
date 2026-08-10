import unittest

from app.runtime.backends.langgraph import build_graph
from app.runtime.backends.langgraph.nodes import ReasoningNode, ToolNode

from tests.runtime.langgraph.test_nodes.test_tool_observation import (
    RecordingToolRunner,
)


class SequenceReasoner:
    def __init__(self):
        self.responses = iter([
            {
                "action": "tool_call", "tool": "crm_query",
                "arguments": {"customer": "A"},
            },
            {"action": "finish", "output": "completed"},
        ])

    def __call__(self, messages):
        return next(self.responses)


class GraphExecutionTest(unittest.TestCase):
    def test_graph_contains_standard_execution_nodes(self):
        nodes = build_graph().get_graph().nodes

        self.assertTrue({
            "context", "reasoning", "tool_decision", "tool",
            "observation", "response",
        }.issubset(nodes))

    def test_graph_runs_reason_tool_observe_response_cycle(self):
        runner = RecordingToolRunner()
        graph = build_graph(
            reasoning_node=ReasoningNode(SequenceReasoner()),
            tool_node=ToolNode(runner),
        )

        result = graph.invoke({
            "trace_id": "trace", "execution_id": "execution",
            "agent_id": "agent", "agent_version": "1", "input": "analyze",
            "messages": [], "tool_results": [],
            "intermediate_results": {},
            "metadata": {"user_id": "user", "role": "sales"},
        })

        self.assertEqual("completed", result["response"])
        self.assertEqual(1, len(runner.calls))
        self.assertEqual({"customer": "A"}, result["tool_results"][0]["output"])
