from app.compiler.backend.models import BackendArtifact
from app.runtime.backends.langgraph.checkpoint import (
    LangGraphCheckpointAdapter, create_in_memory_checkpointer,
)
from app.runtime.backends.langgraph.generator import LangGraphGraphGenerator
from app.runtime.backends.langgraph.state_mapper import LangGraphStateMapper
from langgraph.types import Command
from app.runtime.checkpoint import InMemoryCheckpointStore
from app.runtime.contracts import (
    AgentRuntimeState, ExecutionResult, RuntimeEvent, RuntimeEventType,
)
from app.runtime.ports import GraphRuntime


class LangGraphRuntimeAdapter(GraphRuntime):
    """Execute only compiled LangGraph BackendArtifacts through Runtime Contract v1."""

    def __init__(self, node_adapters=None, checkpoint_store=None, state_mapper=None,
                 graph_generator=None, graph=None, response_event_hook=None,
                 langgraph_checkpointer=None):
        self.state_mapper = state_mapper or LangGraphStateMapper()
        if graph is None and node_adapters is None:
            raise ValueError(
                "LangGraph Runtime requires Backend node adapters or an injected graph"
            )
        self.graph = graph
        self.langgraph_checkpointer = (
            langgraph_checkpointer or create_in_memory_checkpointer()
        )
        self._graphs = {}
        self.graph_generator = graph_generator or (
            LangGraphGraphGenerator(node_adapters)
            if node_adapters is not None else None
        )
        self.checkpoints = LangGraphCheckpointAdapter(
            checkpoint_store or InMemoryCheckpointStore()
        )
        self.response_event_hook = response_event_hook

    def execute(self, artifact, state):
        self._validate_input(artifact, state)
        state.apply_patch({"status": "running"})
        started = RuntimeEvent(RuntimeEventType.WORKER_STARTED, state.task_id)
        graph_span_id = f"{state.execution_id or state.task_id}:graph"
        graph_started = RuntimeEvent(
            RuntimeEventType.GRAPH_STARTED, state.task_id,
            operation_id=graph_span_id, span_id=graph_span_id,
        )
        backend_state = self.state_mapper.to_graph_state(state)
        backend_state["_events"] = [started.to_dict(), graph_started.to_dict()]
        backend_state["_graph_span_id"] = graph_span_id
        self.checkpoints.save(state)
        try:
            graph = self.graph or self._graphs.get(artifact.artifact_id)
            if graph is None:
                graph = self.graph_generator.generate(
                    artifact.runtime_definition,
                    checkpointer=self.langgraph_checkpointer,
                )
                self._graphs[artifact.artifact_id] = graph
            recursion_limit = artifact.runtime_definition.get(
                "execution_policy", {}
            ).get("max_steps", 25)
            output = graph.invoke(
                backend_state,
                config={
                    "recursion_limit": max(1, int(recursion_limit)),
                    "configurable": {"thread_id": state.execution_id or state.task_id},
                },
            )
            if "__interrupt__" in output:
                waiting_state = state.patched({"status": "waiting_approval"})
                self.checkpoints.save(waiting_state)
                return ExecutionResult(
                    task_id=waiting_state.task_id,
                    status="waiting_approval",
                    response=None,
                    state=waiting_state,
                    events=self.state_mapper.events_from_graph_state(output),
                )
            mapped = self.state_mapper.from_graph_state(output)
            final_state = self.state_mapper.apply_result(state, mapped)
            final_state.apply_patch({"status": "completed"})
            events = self.state_mapper.events_from_graph_state(output)
            events.extend([
                RuntimeEvent(RuntimeEventType.WORKER_COMPLETED, state.task_id),
                RuntimeEvent(RuntimeEventType.GRAPH_COMPLETED, state.task_id),
            ])
            self.checkpoints.save(final_state)
            result = ExecutionResult(
                task_id=final_state.task_id,
                status="completed",
                response=final_state.response,
                state=final_state,
                events=events,
            )
            if self.response_event_hook is not None:
                try:
                    self.response_event_hook.emit(artifact, state, result)
                except Exception as error:
                    final_state.metadata.setdefault(
                        "event_hook_errors", []
                    ).append(str(error))
            return result
        except Exception as error:
            failed_state = state.patched({
                "status": "failed",
                "metadata": {**state.metadata, "runtime_error": str(error)},
            })
            events = self.state_mapper.events_from_graph_state(backend_state)
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

    def resume_execution(self, execution_id, approval_result, state=None):
        """Resume a checkpointed LangGraph execution by its stable thread id."""
        graph = self.graph
        if graph is None:
            if state is None:
                state = self.checkpoints.load(execution_id)
            if state is None:
                raise KeyError(f"Checkpoint not found: {execution_id}")
            artifact_id = state.metadata.get("artifact_id")
            graph = self._graphs.get(artifact_id)
            if graph is None:
                raise RuntimeError(
                    "Checkpointed graph is not available; recreate the adapter with the same artifact"
                )
        output = graph.invoke(
            Command(resume=approval_result),
            config={"configurable": {"thread_id": execution_id}},
        )
        if state is None:
            state = self.checkpoints.load(execution_id)
        if state is None:
            raise KeyError(f"Checkpoint not found: {execution_id}")
        mapped = self.state_mapper.from_graph_state(output)
        final_state = self.state_mapper.apply_result(state, mapped)
        final_state.apply_patch({
            "status": "completed" if final_state.response is not None else "failed"
        })
        self.checkpoints.save(final_state)
        return ExecutionResult(
            task_id=final_state.task_id,
            status=final_state.status,
            response=final_state.response,
            state=final_state,
            events=self.state_mapper.events_from_graph_state(output),
        )

    @staticmethod
    def _validate_input(artifact, state):
        if not isinstance(artifact, BackendArtifact):
            raise TypeError("LangGraph runtime requires BackendArtifact")
        if artifact.backend_type != "langgraph":
            raise ValueError(
                f"LangGraph runtime cannot execute backend: {artifact.backend_type}"
            )
        artifact.verify(backend_type="langgraph", production=True)
        if not isinstance(state, AgentRuntimeState):
            raise TypeError("LangGraph runtime requires AgentRuntimeState")
        if (
            artifact.agent_id != state.agent_id
            or artifact.agent_version != state.agent_version
        ):
            raise ValueError("BackendArtifact identity does not match Runtime state")
