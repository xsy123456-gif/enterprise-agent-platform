from langgraph.graph import END, START, StateGraph

from app.runtime.backends.langgraph.state import GraphState


def _passthrough(state: GraphState):
    """Runtime skeleton node with no Agent, Tool, Memory, or business behavior."""
    return dict(state)


def build_graph():
    """Build the smallest invokable LangGraph runtime skeleton."""
    builder = StateGraph(GraphState)
    builder.add_node("runtime_passthrough", _passthrough)
    builder.add_edge(START, "runtime_passthrough")
    builder.add_edge("runtime_passthrough", END)
    return builder.compile()
