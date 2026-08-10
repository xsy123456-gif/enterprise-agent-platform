import unittest

from app.runtime.backends.langgraph import (
    LangGraphRuntimeResult,
    LangGraphStateMapper,
)
from app.runtime.contracts import AgentRuntimeState


def runtime_state():
    return AgentRuntimeState(
        task_id="task",
        trace_id="trace",
        tenant_id="tenant",
        agent_id="agent",
        agent_version="1",
        messages=[{"role": "user", "content": "input"}],
        tool_results=[{"old": True}],
        memory_context={"private": "memory"},
        metadata={"task": "input", "capability": "analysis"},
        execution_id="execution",
        user_id="user",
        department_id="department",
        permission_context={"permissions": ["admin"]},
        policy_context={"policy": "restricted"},
        authorization_result={"allowed": True},
        audit_context={"audit_id": "audit"},
        request_context={"input": "input"},
        memory_policy={"read": ["customer"]},
    )


class LangGraphStateMappingTest(unittest.TestCase):
    def test_runtime_state_maps_explicit_execution_fields(self):
        graph = LangGraphStateMapper().to_graph_state(runtime_state())

        self.assertEqual("trace", graph["trace_id"])
        self.assertEqual("execution", graph["execution_id"])
        self.assertEqual("agent", graph["agent_id"])
        self.assertEqual("input", graph["input"])
        self.assertEqual([{"old": True}], graph["tool_results"])

    def test_graph_state_maps_to_runtime_result_only(self):
        result = LangGraphStateMapper().from_graph_state({
            "messages": [{"role": "assistant", "content": "done"}],
            "tool_results": [{"tool": "result"}],
            "response": "done",
            "current_node": "agent",
            "intermediate_results": {"step": 1},
            "metadata": {"backend": "langgraph"},
        })

        self.assertIsInstance(result, LangGraphRuntimeResult)
        self.assertEqual("done", result.output)
        self.assertEqual("agent", result.current_node)
        self.assertEqual({"step": 1}, result.execution_metadata["intermediate_results"])

    def test_security_audit_and_memory_governance_are_isolated(self):
        graph = LangGraphStateMapper().to_graph_state(runtime_state())

        forbidden = {
            "tenant_id", "user_id", "department_id", "permission_context",
            "permissions", "policy_context", "authorization_result",
            "audit_context", "request_context", "memory_context", "memory_policy",
        }
        self.assertEqual(set(), forbidden.intersection(graph))

    def test_round_trip_preserves_platform_state_and_applies_graph_output(self):
        original = runtime_state()
        mapper = LangGraphStateMapper()
        graph = mapper.to_graph_state(original)
        graph.update({
            "response": "completed",
            "messages": [*graph["messages"], {"role": "assistant", "content": "completed"}],
            "tool_results": [*graph["tool_results"], {"new": True}],
            "current_node": "end",
        })

        restored = mapper.apply_result(original, mapper.from_graph_state(graph))

        self.assertEqual("completed", restored.response)
        self.assertEqual("end", restored.current_node)
        self.assertEqual(original.permission_context, restored.permission_context)
        self.assertEqual(original.audit_context, restored.audit_context)
        self.assertEqual(original.memory_context, restored.memory_context)
        self.assertEqual(original.memory_policy, restored.memory_policy)
