from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    """LangGraph-local execution container; not a platform Agent state."""

    trace_id: str
    execution_id: str
    task_id: str
    tenant_id: str
    agent_id: str
    agent_version: str
    input: str
    messages: list[Any]
    memory_context: Any
    tool_results: list[Any]
    current_node: str | None
    status: str
    plan: Any | None
    response: str | None
    metadata: dict[str, Any]
    _action: dict[str, Any] | None
    _events: list[dict[str, Any]]
