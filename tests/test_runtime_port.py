import unittest

from app.compiler.backend import CurrentBackendCompiler
from app.compiler.models import AgentGraphIR, EdgeIR, NodeIR, NodeType
from app.runtime.contracts import AgentRuntimeState, ExecutionResult
from app.runtime.ports import CurrentRuntimeAdapter, GraphRuntime


class _RuntimeEngine:
    def __init__(self):
        self.calls = []

    def run(self, state, agent_id=None, version=None):
        self.calls.append((state, agent_id, version))
        return "delegated"


def graph():
    return AgentGraphIR(
        agent_id="sales_agent", version="0.2",
        nodes=(NodeIR("start", NodeType.START), NodeIR("end", NodeType.END)),
        edges=(EdgeIR("start", "end"),), state_schema={}, bindings={},
    )


def state():
    return AgentRuntimeState(
        "task", "trace", "tenant", "sales_agent", "0.2",
        messages=[{"role": "user", "content": "task"}],
        metadata={"task": "task", "user_id": "user", "role": "sales"},
    )


class RuntimePortTest(unittest.TestCase):
    def test_current_adapter_returns_execution_result(self):
        engine = _RuntimeEngine()
        adapter = CurrentRuntimeAdapter(engine)
        artifact = CurrentBackendCompiler().compile(graph())

        result = adapter.execute(artifact, state())

        self.assertIsInstance(adapter, GraphRuntime)
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual("completed", result.status)
        self.assertEqual("delegated", result.response)
        self.assertEqual(("sales_agent", "0.2"), engine.calls[0][1:])

    def test_current_adapter_rejects_non_backend_artifact(self):
        with self.assertRaisesRegex(TypeError, "BackendArtifact"):
            CurrentRuntimeAdapter(_RuntimeEngine()).execute(graph(), state())


if __name__ == "__main__":
    unittest.main()
