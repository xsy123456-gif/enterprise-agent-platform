import unittest

from app.compiler.models import AgentGraphIR, NodeIR, NodeType
from app.runtime.ports import CurrentRuntimeAdapter, GraphRuntime


class _RuntimeEngine:
    def __init__(self):
        self.calls = []

    def run(self, state, agent_id=None, version=None):
        self.calls.append((state, agent_id, version))
        return {"output": "delegated"}


class RuntimePortTest(unittest.TestCase):
    def graph(self):
        return AgentGraphIR(
            agent_id="sales_agent", version="0.2",
            nodes=(NodeIR("start", NodeType.START),), edges=(),
            state_schema={}, bindings={},
        )

    def test_current_adapter_implements_runtime_port_and_delegates(self):
        engine = _RuntimeEngine()
        adapter = CurrentRuntimeAdapter(engine)
        state = object()

        self.assertIsInstance(adapter, GraphRuntime)
        self.assertEqual({"output": "delegated"}, adapter.execute(self.graph(), state))
        self.assertEqual([(state, "sales_agent", "0.2")], engine.calls)

    def test_current_adapter_requires_compiled_graph_identity(self):
        with self.assertRaisesRegex(ValueError, "agent_id and version"):
            CurrentRuntimeAdapter(_RuntimeEngine()).execute(object(), object())


if __name__ == "__main__":
    unittest.main()
