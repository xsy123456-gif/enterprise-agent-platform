import unittest

from app.compiler.backend.models import BackendArtifact
from app.runtime.backends.langgraph import LangGraphRuntimeAdapter
from app.runtime.contracts import AgentRuntimeState


class _DeterministicGraph:
    def __init__(self):
        self.configs = []

    def invoke(self, state, config):
        self.configs.append(config)
        state = dict(state)
        state["response"] = "ok"
        state["current_node"] = "done"
        state["status"] = "completed"
        return state


class RuntimeEndToEndContractTest(unittest.TestCase):
    def test_execution_id_is_langgraph_thread_id_and_events_are_returned(self):
        artifact = BackendArtifact.create(
            agent_id="sales_agent", agent_version="0.2", backend_type="langgraph",
            backend_version="1", compiler_version="test", graph_ir_hash="ir",
            runtime_definition={"execution_policy": {"max_steps": 2}},
        )
        state = AgentRuntimeState(
            task_id="task-1", trace_id="trace-1", tenant_id="tenant-1",
            agent_id="sales_agent", agent_version="0.2", execution_id="exec-1",
            request_context={"input": "test"},
        )
        graph = _DeterministicGraph()
        result = LangGraphRuntimeAdapter(graph=graph).execute(artifact, state)
        self.assertEqual("completed", result.status)
        self.assertEqual("ok", result.response)
        self.assertEqual("exec-1", graph.configs[0]["configurable"]["thread_id"])
        self.assertEqual("worker.started", result.events[0].event_type)
        self.assertIn("graph.completed", {event.event_type for event in result.events})


if __name__ == "__main__":
    unittest.main()
