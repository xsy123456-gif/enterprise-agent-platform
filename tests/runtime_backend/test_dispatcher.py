import unittest

from app.compiler.backend import BackendArtifact
from app.runtime.contracts import AgentRuntimeState, ExecutionResult
from app.runtime.dispatcher import (
    AgentRuntimeStateFactory,
    BackendArtifactResolver,
    RuntimeDispatcher,
)
from app.runtime.ports import GraphRuntime


class FakeBackend(GraphRuntime):
    def __init__(self):
        self.calls = []

    def execute(self, artifact, state):
        self.calls.append((artifact, state))
        return ExecutionResult(
            task_id=state.task_id, status="completed", response="ok", state=state,
        )


class Definition:
    runtime = {}


class Context:
    task_id = "task"
    trace_id = "trace"
    tenant_id = "tenant"
    task = "goal"
    user_id = "user"
    role = "role"
    step_id = "1"
    capability = "customer_analysis"
    goal = "goal"
    memory_context = []
    messages = [{"role": "user", "content": "goal"}]
    tool_results = []
    department_id = None
    agent_definition = Definition()


class RuntimeDispatcherTest(unittest.TestCase):
    def test_dispatcher_selects_backend_and_executes_contract(self):
        backend = FakeBackend()
        artifact = BackendArtifact.create(
            agent_id="agent", agent_version="1", backend_type="current",
            backend_version="1", compiler_version="test", graph_ir_hash="g",
            runtime_definition={},
        )
        from app.runtime.selector import RuntimeSelector
        dispatcher = RuntimeDispatcher(
            RuntimeSelector({"current": backend}, default_backend="current"),
            BackendArtifactResolver({("agent", "1", "current"): artifact}),
            AgentRuntimeStateFactory(),
        )

        result = dispatcher.execute_step(Context(), "agent", "1")

        self.assertEqual("ok", result.response)
        self.assertEqual(1, len(backend.calls))
        self.assertIsInstance(backend.calls[0][1], AgentRuntimeState)
