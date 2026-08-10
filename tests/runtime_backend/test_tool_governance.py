import unittest

from app.agents.definition import AgentDefinition
from app.compiler.backend.langgraph import LangGraphBackendCompiler
from app.compiler.models import AgentGraphIR, EdgeIR, EdgeType, NodeIR, NodeType
from app.runtime.backends.langgraph import (
    LangGraphNodeAdapterRegistry, LangGraphRuntimeAdapter,
)
from app.runtime.contracts import AgentRuntimeState
from app.runtime.tool_runner import ToolRunner
from app.tools.registry import ToolRegistry


class _Agent:
    def __init__(self):
        self.calls = 0

    def reason(self, messages):
        self.calls += 1
        if self.calls == 1:
            return {"action": "tool_call", "tool": "crm_query", "arguments": {"id": "A"}}
        return {"action": "finish", "output": "tool observed"}


class _Record:
    def __init__(self):
        self.instance = _Agent()
        self.definition = AgentDefinition(
            "sales_agent", "1.0", "prompt", capabilities=["customer_analysis"],
            allowed_tools=["crm_query"],
        )


class _Registry:
    def __init__(self):
        self.record = _Record()

    def get(self, agent_id, version=None):
        return self.record

    def get_tool_bindings(self, capability):
        return []


class _Tool:
    def validate_input(self, value):
        return isinstance(value, dict) and "id" in value

    def execute(self, value):
        return {"customer": value["id"]}


class _Permission:
    def __init__(self):
        self.checks = []

    def check(self, role, tool):
        self.checks.append((role, tool))
        return True


class _Audit:
    def __init__(self):
        self.records = []

    def record(self, **record):
        self.records.append(record)


class _Events:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)


def graph():
    return AgentGraphIR(
        "sales_agent", "1.0",
        nodes=(
            NodeIR("start", NodeType.START), NodeIR("agent", NodeType.AGENT),
            NodeIR("tool:crm_query", NodeType.TOOL, bindings={"tool_name": "crm_query"}),
            NodeIR("end", NodeType.END),
        ),
        edges=(
            EdgeIR("start", "agent"),
            EdgeIR(
                "agent", "tool:crm_query", "action.tool == 'crm_query'",
                EdgeType.CONDITIONAL,
            ),
            EdgeIR("tool:crm_query", "agent"),
            EdgeIR("agent", "end", "action == 'finish'", EdgeType.CONDITIONAL),
        ),
        state_schema={}, bindings={}, execution_policy={"max_steps": 10},
    )


class ToolGovernanceTest(unittest.TestCase):
    def test_tool_node_uses_validator_runner_permission_and_audit(self):
        tools = ToolRegistry()
        tools.register("crm_query", _Tool())
        permission, audit, events = _Permission(), _Audit(), _Events()
        runner = ToolRunner(tools, permission, audit, events)
        registry = _Registry()
        runtime = LangGraphRuntimeAdapter(LangGraphNodeAdapterRegistry(
            agent_registry=registry, tool_runner=runner,
        ))
        state = AgentRuntimeState(
            "task", "trace", "tenant", "sales_agent", "1.0",
            messages=[{"role": "user", "content": "analyze"}],
            metadata={
                "task": "analyze", "user_id": "user", "role": "sales",
                "capability": "customer_analysis",
            },
        )

        result = runtime.execute(LangGraphBackendCompiler().compile(graph()), state)

        self.assertEqual("completed", result.status)
        self.assertEqual([("sales", "crm_query")], permission.checks)
        self.assertEqual("allow", audit.records[0]["action"])
        self.assertEqual([{"customer": "A"}], result.state.tool_results)
        self.assertEqual("tool_completed", events.events[0].event_type)
