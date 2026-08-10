from app.runtime.backends.langgraph.state import GraphState as LangGraphState
from app.runtime.backends.langgraph.state_mapper import LangGraphStateMapper
from app.runtime.contracts import AgentRuntimeState


class LangGraphStateAdapter(LangGraphStateMapper):
    """Backward-compatible adapter names over the canonical state mapper."""

    def to_backend(self, state: AgentRuntimeState) -> LangGraphState:
        return self.to_graph_state(state)

    def from_backend(self, payload) -> AgentRuntimeState:
        return self.from_graph_state(payload)

    @staticmethod
    def events_from_backend(payload):
        return LangGraphStateMapper.events_from_graph_state(payload)
