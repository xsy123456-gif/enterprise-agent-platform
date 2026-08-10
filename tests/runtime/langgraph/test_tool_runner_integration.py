import unittest

from app.audit.logger import AuditLogger
from app.events.bus import EventBus
from app.permission.rbac import PermissionManager
from app.runtime.backends.langgraph import build_graph
from app.runtime.backends.langgraph.nodes import ReasoningNode, ToolNode
from app.runtime.contracts import AgentRuntimeState
from app.runtime.tool_runner import ToolRunner
from app.tools.models import ToolCallRequest, ToolResult
from app.tools.registry import ToolRegistry


class SimpleTool:
    def validate_input(self, value):
        return isinstance(value, dict) and bool(value.get("customer"))

    def execute(self, value):
        return {"customer": value["customer"], "status": "found"}


class DenyPermission:
    def check(self, role, tool_name):
        return False


class ToolRunnerIntegrationTest(unittest.TestCase):
    def runner(self, permission=None):
        registry = ToolRegistry()
        registry.register("crm_query", SimpleTool())
        events = EventBus()
        audit = AuditLogger()
        return ToolRunner(
            registry, permission or PermissionManager(), audit, events
        ), audit, events

    def request(self, role="sales"):
        return ToolCallRequest(
            tool_name="crm_query", arguments={"customer": "customer_A"},
            trace_id="trace", execution_id="execution", agent_id="agent",
            user_id="user", role=role,
        )

    def test_tool_node_uses_toolrunner_execute_contract(self):
        runner, _, _ = self.runner()
        result = runner.execute(self.request())

        self.assertIsInstance(result, ToolResult)
        self.assertTrue(result.success)

    def test_permission_denied_prevents_tool_execution(self):
        runner, _, events = self.runner(DenyPermission())
        tool = runner.registry.get("crm_query")
        calls = []
        original = tool.execute
        tool.execute = lambda value: (calls.append(value), original(value))[1]

        result = runner.execute(self.request())

        self.assertFalse(result.success)
        self.assertEqual([], calls)
        self.assertIn("tool.denied", [event.event_type for event in events.events])

    def test_tool_lifecycle_emits_called_and_completed(self):
        runner, _, events = self.runner()

        runner.execute(self.request())

        self.assertEqual(
            ["tool.called", "tool.completed"],
            [event.event_type for event in events.events],
        )

    def test_graph_tool_result_round_trip(self):
        runner, _, _ = self.runner()

        class Reasoner:
            def __init__(self):
                self.responses = iter([
                    {"action": "tool_call", "tool": "crm_query",
                     "arguments": {"customer": "customer_A"}},
                    {"action": "finish", "output": "customer found"},
                ])

            def __call__(self, messages):
                return next(self.responses)

        graph = build_graph(
            reasoning_node=ReasoningNode(Reasoner()),
            tool_node=ToolNode(runner),
        )
        result = graph.invoke({
            "trace_id": "trace", "execution_id": "execution",
            "agent_id": "agent", "agent_version": "1", "input": "find",
            "messages": [], "tool_results": [], "intermediate_results": {},
            "metadata": {"user_id": "user", "role": "sales"},
        })

        self.assertEqual("customer found", result["response"])
        self.assertEqual("found", result["tool_results"][0]["output"]["status"])
