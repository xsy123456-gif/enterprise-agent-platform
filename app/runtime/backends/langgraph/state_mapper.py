from app.runtime.backends.langgraph.state import GraphState
from app.runtime.contracts import AgentRuntimeState, RuntimeEvent


class LangGraphStateMapper:
    """Pure mapping between Runtime Contract v1 and LangGraph-local state."""

    CONTRACT_FIELDS = set(AgentRuntimeState.__dataclass_fields__)

    def to_graph_state(self, runtime_state: AgentRuntimeState) -> GraphState:
        if not isinstance(runtime_state, AgentRuntimeState):
            raise TypeError("LangGraph runtime requires AgentRuntimeState")
        metadata = dict(runtime_state.metadata)
        return {
            **runtime_state.to_dict(),
            "execution_id": metadata.get("execution_id", runtime_state.task_id),
            "input": metadata.get("task", ""),
            "_action": None,
            "_events": [],
        }

    def from_graph_state(self, graph_state) -> AgentRuntimeState:
        return AgentRuntimeState.from_dict({
            key: value for key, value in dict(graph_state).items()
            if key in self.CONTRACT_FIELDS
        })

    @staticmethod
    def events_from_graph_state(graph_state):
        return [
            RuntimeEvent.from_dict(item)
            for item in graph_state.get("_events", [])
        ]
