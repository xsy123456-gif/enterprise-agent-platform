from langgraph.graph import END, START, StateGraph

from app.runtime.backends.langgraph.nodes import (
    ContextNode,
    ObservationNode,
    ReasoningNode,
    ResponseNode,
    ToolDecisionNode,
    ToolNode,
    GuardNode,
    GovernanceGate,
    ApprovalInterruptNode,
)
from app.runtime.backends.langgraph.state import GraphState


def _route_decision(state):
    action = state.get("_action") or {}
    return "tool" if action.get("type") == "tool" else "response"


def _route_governance(state):
    status = (state.get("governance_decision") or {}).get("status", "allow")
    return {"allow": "tool", "require_approval": "approval", "deny": "response"}.get(status, "response")


def _route_approval(state):
    return "tool" if (state.get("governance_decision") or {}).get("status") == "allow" else "response"


def build_graph(
    context_node=None,
    reasoning_node=None,
    tool_decision_node=None,
    tool_node=None,
    observation_node=None,
    response_node=None,
    guard_node=None,
    governance_gate=None,
    approval_node=None,
    checkpointer=None,
):
    """Build the standard Agent internal execution graph."""
    builder = StateGraph(GraphState)
    builder.add_node("context", context_node or ContextNode())
    builder.add_node("guard", guard_node or GuardNode())
    builder.add_node("reasoning", reasoning_node or ReasoningNode())
    builder.add_node(
        "tool_decision", tool_decision_node or ToolDecisionNode()
    )
    builder.add_node("tool", tool_node or ToolNode())
    builder.add_node("observation", observation_node or ObservationNode())
    builder.add_node("response", response_node or ResponseNode())
    builder.add_node("governance_gate", governance_gate or GovernanceGate())
    builder.add_node("approval", approval_node or ApprovalInterruptNode())

    builder.add_edge(START, "context")
    builder.add_edge("context", "guard")
    builder.add_edge("guard", "reasoning")
    builder.add_edge("reasoning", "tool_decision")
    builder.add_conditional_edges(
        "tool_decision",
        _route_decision,
        {"tool": "governance_gate", "response": "response"},
    )
    builder.add_conditional_edges("governance_gate", _route_governance)
    builder.add_conditional_edges("approval", _route_approval)
    builder.add_edge("tool", "observation")
    builder.add_edge("observation", "reasoning")
    builder.add_edge("response", END)
    return builder.compile(checkpointer=checkpointer) if checkpointer is not None else builder.compile()
