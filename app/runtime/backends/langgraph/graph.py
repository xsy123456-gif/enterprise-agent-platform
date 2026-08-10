from langgraph.graph import END, START, StateGraph

from app.runtime.backends.langgraph.nodes import (
    ContextNode,
    ObservationNode,
    ReasoningNode,
    ResponseNode,
    ToolDecisionNode,
    ToolNode,
)
from app.runtime.backends.langgraph.state import GraphState


def _route_decision(state):
    action = state.get("_action") or {}
    return "tool" if action.get("type") == "tool" else "response"


def build_graph(
    context_node=None,
    reasoning_node=None,
    tool_decision_node=None,
    tool_node=None,
    observation_node=None,
    response_node=None,
):
    """Build the standard Agent internal execution graph."""
    builder = StateGraph(GraphState)
    builder.add_node("context", context_node or ContextNode())
    builder.add_node("reasoning", reasoning_node or ReasoningNode())
    builder.add_node(
        "tool_decision", tool_decision_node or ToolDecisionNode()
    )
    builder.add_node("tool", tool_node or ToolNode())
    builder.add_node("observation", observation_node or ObservationNode())
    builder.add_node("response", response_node or ResponseNode())

    builder.add_edge(START, "context")
    builder.add_edge("context", "reasoning")
    builder.add_edge("reasoning", "tool_decision")
    builder.add_conditional_edges(
        "tool_decision",
        _route_decision,
        {"tool": "tool", "response": "response"},
    )
    builder.add_edge("tool", "observation")
    builder.add_edge("observation", "reasoning")
    builder.add_edge("response", END)
    return builder.compile()
