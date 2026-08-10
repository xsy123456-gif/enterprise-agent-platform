from app.compiler.backend.models import BackendArtifact
from app.runtime.backends.langgraph.checkpoint import LangGraphCheckpointAdapter
from app.runtime.backends.langgraph.generator import LangGraphGraphGenerator
from app.runtime.backends.langgraph.state_adapter import LangGraphStateAdapter
from app.runtime.checkpoint import InMemoryCheckpointStore
from app.runtime.contracts import (
    AgentRuntimeState, ExecutionResult, RuntimeEvent, RuntimeEventType,
)
from app.runtime.ports import GraphRuntime


class LangGraphRuntimeAdapter(GraphRuntime):
    """Execute only compiled LangGraph BackendArtifacts through Runtime Contract v1."""

    def __init__(self, node_adapters, checkpoint_store=None, state_adapter=None,
                 graph_generator=None):
        self.state_adapter = state_adapter or LangGraphStateAdapter()
        self.graph_generator = graph_generator or LangGraphGraphGenerator(node_adapters)
        self.checkpoints = LangGraphCheckpointAdapter(
            checkpoint_store or InMemoryCheckpointStore()
        )

    def execute(self, artifact, state):
        self._validate_input(artifact, state)
        state.apply_patch({"status": "running"})
        started = RuntimeEvent(RuntimeEventType.WORKER_STARTED, state.task_id)
        backend_state = self.state_adapter.to_backend(state)
        backend_state["_events"] = [started.to_dict()]
        self.checkpoints.save(state)
        try:
            graph = self.graph_generator.generate(artifact.runtime_definition)
            recursion_limit = artifact.runtime_definition.get(
                "execution_policy", {}
            ).get("max_steps", 25)
            output = graph.invoke(
                backend_state,
                config={"recursion_limit": max(1, int(recursion_limit))},
            )
            final_state = self.state_adapter.from_backend(output)
            final_state.apply_patch({"status": "completed"})
            events = self.state_adapter.events_from_backend(output)
            events.extend([
                RuntimeEvent(RuntimeEventType.WORKER_COMPLETED, state.task_id),
                RuntimeEvent(RuntimeEventType.GRAPH_COMPLETED, state.task_id),
            ])
            self.checkpoints.save(final_state)
            return ExecutionResult(
                task_id=final_state.task_id,
                status="completed",
                response=final_state.response,
                state=final_state,
                events=events,
            )
        except Exception as error:
            failed_state = state.patched({
                "status": "failed",
                "metadata": {**state.metadata, "runtime_error": str(error)},
            })
            events = self.state_adapter.events_from_backend(backend_state)
            events.append(RuntimeEvent(
                RuntimeEventType.GRAPH_FAILED, state.task_id,
                payload={"error": str(error)},
            ))
            self.checkpoints.save(failed_state)
            return ExecutionResult(
                task_id=failed_state.task_id,
                status="failed",
                response=None,
                state=failed_state,
                events=events,
            )

    @staticmethod
    def _validate_input(artifact, state):
        if not isinstance(artifact, BackendArtifact):
            raise TypeError("LangGraph runtime requires BackendArtifact")
        if artifact.backend_type != "langgraph":
            raise ValueError(
                f"LangGraph runtime cannot execute backend: {artifact.backend_type}"
            )
        if not isinstance(state, AgentRuntimeState):
            raise TypeError("LangGraph runtime requires AgentRuntimeState")
        if (
            artifact.agent_id != state.agent_id
            or artifact.agent_version != state.agent_version
        ):
            raise ValueError("BackendArtifact identity does not match Runtime state")
