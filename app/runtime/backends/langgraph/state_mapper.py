from dataclasses import dataclass, field
from typing import Any

from app.runtime.backends.langgraph.state import GraphState
from app.runtime.contracts import AgentRuntimeState, RuntimeEvent


@dataclass(frozen=True)
class LangGraphRuntimeResult:
    output: str | None = None
    messages: list[Any] = field(default_factory=list)
    tool_results: list[Any] = field(default_factory=list)
    execution_metadata: dict[str, Any] = field(default_factory=dict)
    current_node: str | None = None


class LangGraphStateMapper:
    """The only boundary between platform state and LangGraph state."""

    def to_graph_state(self, runtime_state: AgentRuntimeState) -> GraphState:
        if not isinstance(runtime_state, AgentRuntimeState):
            raise TypeError("LangGraph runtime requires AgentRuntimeState")
        execution_id = (
            runtime_state.execution_id
            or runtime_state.metadata.get("execution_id")
            or runtime_state.task_id
        )
        input_text = (
            runtime_state.request_context.get("input")
            or runtime_state.metadata.get("task")
            or ""
        )
        # Explicit allow-list: platform security, audit, tenant and memory policy
        # fields are intentionally absent from this mapping.
        return {
            "trace_id": runtime_state.trace_id,
            "execution_id": execution_id,
            "agent_id": runtime_state.agent_id,
            "agent_version": runtime_state.agent_version,
            "input": input_text,
            "messages": list(runtime_state.messages),
            "current_node": runtime_state.current_node,
            "intermediate_results": {},
            "tool_results": list(runtime_state.tool_results),
            "metadata": dict(runtime_state.metadata),
            "status": runtime_state.status,
            "response": runtime_state.response,
            "_action": None,
            "_events": [],
        }

    def from_graph_state(self, graph_state) -> LangGraphRuntimeResult:
        state = dict(graph_state)
        return LangGraphRuntimeResult(
            output=state.get("response"),
            messages=list(state.get("messages") or []),
            tool_results=list(state.get("tool_results") or []),
            execution_metadata={
                "current_node": state.get("current_node"),
                "intermediate_results": dict(
                    state.get("intermediate_results") or {}
                ),
                "graph_metadata": dict(state.get("metadata") or {}),
            },
            current_node=state.get("current_node"),
        )

    @staticmethod
    def apply_result(
        runtime_state: AgentRuntimeState,
        result: LangGraphRuntimeResult,
    ) -> AgentRuntimeState:
        execution_metadata = dict(result.execution_metadata)
        graph_metadata = execution_metadata.get("graph_metadata", {})
        has_execution_change = bool(
            result.current_node
            or execution_metadata.get("intermediate_results")
            or graph_metadata != runtime_state.metadata
        )
        metadata = dict(runtime_state.metadata)
        if has_execution_change:
            metadata["langgraph_execution"] = execution_metadata
        return runtime_state.patched({
            "messages": list(result.messages),
            "tool_results": list(result.tool_results),
            "response": result.output,
            "current_node": result.current_node,
            "metadata": metadata,
        })

    @staticmethod
    def events_from_graph_state(graph_state):
        return [
            RuntimeEvent.from_dict(item)
            for item in graph_state.get("_events", [])
        ]
