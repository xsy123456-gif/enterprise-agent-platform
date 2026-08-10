import unittest

from app.compiler.backend import BackendArtifact
from app.runtime.contracts import AgentRuntimeState, ExecutionResult, RuntimeEvent, RuntimeEventType
from app.runtime.dispatcher import BackendArtifactResolver, RuntimeDispatcher
from app.runtime.governance.events import RuntimeEvent as GovernanceRuntimeEvent
from app.runtime.ports import GraphRuntime
from app.runtime.selector import RuntimeSelector
from app.storage.providers.memory import InMemoryEventStore


class EventBackend(GraphRuntime):
    def execute(self, artifact, state):
        return ExecutionResult(
            task_id=state.task_id, status="completed", response="ok", state=state,
            events=[
                RuntimeEvent(RuntimeEventType.WORKER_STARTED, state.task_id),
                RuntimeEvent(RuntimeEventType.GRAPH_COMPLETED, state.task_id),
            ],
        )


class GovernanceBridgeTest(unittest.TestCase):
    def test_runtime_events_reach_event_store(self):
        artifact = BackendArtifact.create(
            agent_id="agent", agent_version="1", backend_type="current",
            backend_version="1", compiler_version="test", graph_ir_hash="g",
            runtime_definition={},
        )
        store = InMemoryEventStore()
        dispatcher = RuntimeDispatcher(
            RuntimeSelector(
                {"current": EventBackend()}, default_backend="current"
            ),
            BackendArtifactResolver({("agent", "1", "current"): artifact}),
            event_store=store,
        )
        from tests.runtime_backend.test_dispatcher import Context
        result = dispatcher.execute_step(Context(), "agent", "1")

        self.assertEqual("ok", result.response)
        events = store.query(execution_id="task")
        self.assertEqual(["worker.started", "graph.completed"],
                         [event.event_type for event in events])
        self.assertTrue(all(isinstance(event, GovernanceRuntimeEvent) for event in events))
        with self.assertRaises(Exception):
            store.append(events[0])
