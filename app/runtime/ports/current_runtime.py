from app.compiler.backend.models import BackendArtifact
from app.runtime.context import AgentContext
from app.runtime.contracts import (
    AgentRuntimeState, ExecutionResult, RuntimeEvent, RuntimeEventType,
)
from app.runtime.ports.graph_runtime import GraphRuntime


class CurrentRuntimeAdapter(GraphRuntime):
    """GraphRuntime adapter over the existing RuntimeEngine.

    It deliberately delegates to RuntimeEngine instead of duplicating the
    current AgentExecutionLoop, ToolRunner, Memory, or EventBus behavior.
    """

    def __init__(self, runtime_engine):
        self.runtime_engine = runtime_engine

    def execute(self, artifact, state):
        self._validate_input(artifact, state)
        state.apply_patch({"status": "running"})
        events = [RuntimeEvent(RuntimeEventType.WORKER_STARTED, state.task_id)]
        context = self._to_current_context(state)
        try:
            response = self.runtime_engine.run(
                context,
                agent_id=artifact.agent_id,
                version=artifact.agent_version,
            )
            state.apply_patch({
                "status": "completed",
                "messages": list(context.messages),
                "tool_results": list(context.tool_results),
                "response": response,
            })
            events.extend([
                RuntimeEvent(RuntimeEventType.WORKER_COMPLETED, state.task_id),
                RuntimeEvent(RuntimeEventType.GRAPH_COMPLETED, state.task_id),
            ])
            return ExecutionResult(
                state.task_id, "completed", response, state, events,
            )
        except Exception as error:
            state.apply_patch({
                "status": "failed",
                "metadata": {**state.metadata, "runtime_error": str(error)},
            })
            events.append(RuntimeEvent(
                RuntimeEventType.GRAPH_FAILED, state.task_id,
                payload={"error": str(error)},
            ))
            return ExecutionResult(state.task_id, "failed", None, state, events)

    @staticmethod
    def _validate_input(artifact, state):
        if not isinstance(artifact, BackendArtifact):
            raise TypeError("Current runtime requires BackendArtifact")
        if artifact.backend_type != "current":
            raise ValueError(
                f"Current runtime cannot execute backend: {artifact.backend_type}"
            )
        if not isinstance(state, AgentRuntimeState):
            raise TypeError("Current runtime requires AgentRuntimeState")
        if (
            artifact.agent_id != state.agent_id
            or artifact.agent_version != state.agent_version
        ):
            raise ValueError("BackendArtifact identity does not match Runtime state")

    @staticmethod
    def _to_current_context(state):
        metadata = state.metadata
        for name in ("task", "user_id", "role"):
            if not metadata.get(name):
                raise ValueError(f"Current runtime requires metadata.{name}")
        context = AgentContext(
            task=metadata["task"], user_id=metadata["user_id"], role=metadata["role"],
            agent_name=state.agent_id, task_id=state.task_id,
            step_id=metadata.get("step_id"), capability=metadata.get("capability"),
            goal=metadata.get("goal"), memory_context=state.memory_context,
            tenant_id=state.tenant_id, department_id=metadata.get("department_id"),
        )
        context.trace_id = state.trace_id
        context.messages = list(state.messages) or context.messages
        context.tool_results = list(state.tool_results)
        return context
