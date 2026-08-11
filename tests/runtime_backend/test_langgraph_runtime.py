import json
import unittest

from app.agents.definition import AgentDefinition
from app.compiler.backend.langgraph import LangGraphBackendCompiler
from app.compiler.models import AgentGraphIR, EdgeIR, EdgeType, NodeIR, NodeType
from app.runtime.backends.langgraph import (
    LangGraphNodeAdapterRegistry, LangGraphRuntimeAdapter,
)
from app.runtime.checkpoint import InMemoryCheckpointStore
from app.runtime.contracts import AgentRuntimeState, ExecutionResult, RuntimeEventType


class _Agent:
    def __init__(self, responses):
        self.responses = iter(responses)

    def reason(self, messages):
        return next(self.responses)


class _Record:
    def __init__(self, agent, tools=None):
        self.instance = agent
        self.definition = AgentDefinition(
            "sales_agent", "1.0", "system prompt",
            capabilities=["customer_analysis"], allowed_tools=list(tools or []),
        )


class _Registry:
    def __init__(self, record):
        self.record = record

    def get(self, agent_id, version=None):
        if (agent_id, version) != ("sales_agent", "1.0"):
            raise KeyError(agent_id)
        return self.record

    def get_tool_bindings(self, capability):
        return []


def finish_graph():
    return AgentGraphIR(
        "sales_agent", "1.0",
        nodes=(
            NodeIR("start", NodeType.START),
            NodeIR("agent", NodeType.AGENT),
            NodeIR("end", NodeType.END),
        ),
        edges=(
            EdgeIR("start", "agent"),
            EdgeIR("agent", "end", "action == 'finish'", EdgeType.CONDITIONAL),
        ),
        state_schema={"messages": "list"}, bindings={},
        execution_policy={"max_steps": 10},
    )


class LangGraphRuntimeTest(unittest.TestCase):
    def test_runtime_requires_artifact_driven_node_adapters(self):
        with self.assertRaisesRegex(ValueError, "Backend node adapters"):
            LangGraphRuntimeAdapter()

    def test_execute_artifact_and_result_conversion(self):
        registry = _Registry(_Record(_Agent([
            {"action": "finish", "output": "done"},
        ])))
        store = InMemoryCheckpointStore()
        runtime = LangGraphRuntimeAdapter(
            LangGraphNodeAdapterRegistry(agent_registry=registry),
            checkpoint_store=store,
        )
        artifact = LangGraphBackendCompiler().compile(finish_graph())
        state = AgentRuntimeState(
            "task-1", "trace-1", "tenant-1", "sales_agent", "1.0",
            messages=[{"role": "user", "content": "analyze"}],
            metadata={"execution_id": "execution-1"},
        )

        result = runtime.execute(artifact, state)

        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual("completed", result.status)
        self.assertEqual("done", result.response)
        self.assertEqual("completed", store.load("execution-1").status)
        self.assertIn(RuntimeEventType.GRAPH_COMPLETED, [
            event.event_type for event in result.events
        ])
        self.assertEqual(result.to_dict(), ExecutionResult.from_dict(
            json.loads(json.dumps(result.to_dict()))
        ).to_dict())

    def test_runtime_rejects_graph_ir_input(self):
        registry = _Registry(_Record(_Agent([])))
        runtime = LangGraphRuntimeAdapter(
            LangGraphNodeAdapterRegistry(agent_registry=registry)
        )
        state = AgentRuntimeState(
            "task", "trace", "tenant", "sales_agent", "1.0"
        )
        with self.assertRaisesRegex(TypeError, "BackendArtifact"):
            runtime.execute(finish_graph(), state)
