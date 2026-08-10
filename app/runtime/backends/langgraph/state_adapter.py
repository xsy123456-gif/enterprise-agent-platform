from typing import Any, TypedDict

from app.runtime.contracts import AgentRuntimeState, RuntimeEvent


class LangGraphState(TypedDict, total=False):
    task_id: str
    trace_id: str
    tenant_id: str
    agent_id: str
    agent_version: str
    current_node: str | None
    status: str
    messages: list[Any]
    plan: Any | None
    memory_context: Any | None
    tool_results: list[Any]
    response: str | None
    metadata: dict[str, Any]
    _action: dict[str, Any] | None
    _events: list[dict[str, Any]]


class LangGraphStateAdapter:
    """Pure translation; it does not access Memory, Tools, Audit, or EventBus."""

    CONTRACT_FIELDS = set(AgentRuntimeState.__dataclass_fields__)

    def to_backend(self, state: AgentRuntimeState) -> LangGraphState:
        if not isinstance(state, AgentRuntimeState):
            raise TypeError("LangGraph runtime requires AgentRuntimeState")
        return {
            **state.to_dict(),
            "_action": None,
            "_events": [],
        }

    def from_backend(self, payload) -> AgentRuntimeState:
        return AgentRuntimeState.from_dict({
            key: value for key, value in dict(payload).items()
            if key in self.CONTRACT_FIELDS
        })

    @staticmethod
    def events_from_backend(payload):
        return [RuntimeEvent.from_dict(item) for item in payload.get("_events", [])]
