import unittest

from app.compiler.backend import CurrentBackendCompiler
from app.compiler.models import AgentGraphIR, EdgeIR, NodeIR, NodeType
from app.runtime.contracts import AgentRuntimeState
from app.runtime.ports import CurrentRuntimeAdapter, GraphRuntime
from app.runtime.selector import RuntimeSelector


class RecordingEngine:
    def __init__(self):
        self.calls = []

    def run(self, state, agent_id=None, version=None):
        self.calls.append((state, agent_id, version))
        return "response"


def artifact():
    graph = AgentGraphIR(
        agent_id="sales_agent", version="0.2",
        nodes=(NodeIR("start", NodeType.START), NodeIR("end", NodeType.END)),
        edges=(EdgeIR("start", "end"),), state_schema={}, bindings={},
    )
    return CurrentBackendCompiler().compile(graph)


def state():
    return AgentRuntimeState(
        "task", "trace", "tenant", "sales_agent", "0.2",
        metadata={"task": "task", "user_id": "user", "role": "sales"},
    )


class CurrentBackendProductionTest(unittest.TestCase):
    def test_current_backend_is_selected_and_delegates_without_legacy_leak(self):
        engine = RecordingEngine()
        backend = CurrentRuntimeAdapter(engine)
        selector = RuntimeSelector({"current": backend}, default_backend="current")

        selected = selector.select("sales_agent", "0.2")
        result = selected.execute(artifact(), state())

        self.assertIsInstance(selected, GraphRuntime)
        self.assertEqual("response", result.response)
        self.assertEqual("sales_agent", engine.calls[0][1])
        self.assertFalse(hasattr(result, "context"))
