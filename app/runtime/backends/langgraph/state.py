from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    """LangGraph-local execution container; not a platform Agent state."""

    trace_id: str
    execution_id: str
    agent_id: str
    agent_version: str
    input: str
    messages: list[Any]
    tool_results: list[Any]
    pending_tool_call: dict[str, Any] | None
    current_node: str | None
    intermediate_results: dict[str, Any]
    metadata: dict[str, Any]
    guard_result: dict[str, Any]
    governance_decision: dict[str, Any]

    # Backend-private execution fields; never contain platform governance state.
    reasoning_output: Any
    tool_call_request: dict[str, Any] | None
    observation: Any
    status: str
    response: str | None
    _action: dict[str, Any] | None
    _events: list[dict[str, Any]]
