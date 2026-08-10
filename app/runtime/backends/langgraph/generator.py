import re
import uuid

from langgraph.graph import END, START, StateGraph

from app.runtime.backends.langgraph.state_adapter import LangGraphState
from app.runtime.contracts import RuntimeEvent, RuntimeEventType


class LangGraphGraphGenerator:
    """Materialize a process-local StateGraph from a serialized artifact."""

    def __init__(self, node_adapters):
        self.node_adapters = node_adapters

    def generate(self, runtime_definition):
        if runtime_definition.get("schema_version") != "langgraph.backend/v1":
            raise ValueError("Unsupported LangGraph backend artifact schema")
        builder = StateGraph(LangGraphState)
        node_ids = {
            node["id"]: self._backend_node_id(position, node["id"])
            for position, node in enumerate(runtime_definition["nodes"])
        }
        for node in runtime_definition["nodes"]:
            adapter = self.node_adapters.build(node)
            builder.add_node(
                node_ids[node["id"]], self._instrument(node["id"], adapter)
            )

        conditional = {}
        for edge in runtime_definition["edges"]:
            if edge["edge_type"] == "NORMAL":
                builder.add_edge(
                    self._endpoint(
                        edge["source"], runtime_definition, node_ids, source=True
                    ),
                    self._endpoint(
                        edge["target"], runtime_definition, node_ids, source=False
                    ),
                )
            else:
                conditional.setdefault(edge["source"], []).append(edge)

        for source, edges in conditional.items():
            path_map = {
                edge["target"]: self._endpoint(
                    edge["target"], runtime_definition, node_ids, source=False
                )
                for edge in edges
            }
            builder.add_conditional_edges(
                self._endpoint(source, runtime_definition, node_ids, source=True),
                self._router(edges),
                path_map,
            )
        return builder.compile()

    @staticmethod
    def _endpoint(node_id, definition, node_ids, source):
        if node_id == definition["start_node"]:
            if not source:
                raise ValueError("START node cannot be an edge target")
            return START
        if node_id in definition["end_nodes"]:
            if source:
                raise ValueError("END node cannot be an edge source")
            return END
        try:
            return node_ids[node_id]
        except KeyError as error:
            raise ValueError(f"Backend edge references unknown node: {node_id}") from error

    @staticmethod
    def _backend_node_id(position, platform_node_id):
        normalized = re.sub(r"[^A-Za-z0-9_-]", "_", platform_node_id)
        return f"node_{position}_{normalized}"

    @staticmethod
    def _instrument(node_id, adapter):
        def execute(state):
            operation_id = str(uuid.uuid4())
            span_id = str(uuid.uuid4())
            events = list(state.get("_events") or [])
            events.append(RuntimeEvent(
                RuntimeEventType.NODE_STARTED, state["execution_id"], node_id,
                operation_id=operation_id, span_id=span_id,
                parent_span_id=state.get("_graph_span_id"),
            ).to_dict())
            try:
                patch = dict(adapter(state) or {})
            except Exception as error:
                events.append(RuntimeEvent(
                    RuntimeEventType.NODE_FAILED, state["execution_id"], node_id,
                    payload={"error": str(error)}, operation_id=operation_id,
                    span_id=span_id, parent_span_id=state.get("_graph_span_id"),
                ).to_dict())
                state["_events"] = events
                raise
            patch["current_node"] = node_id
            events.append(RuntimeEvent(
                RuntimeEventType.NODE_COMPLETED, state["execution_id"], node_id,
                operation_id=operation_id, span_id=span_id,
                parent_span_id=state.get("_graph_span_id"),
            ).to_dict())
            patch["_events"] = events
            return patch
        return execute

    @classmethod
    def _router(cls, edges):
        def route(state):
            for edge in edges:
                if cls._matches(edge, state):
                    return edge["target"]
            raise RuntimeError(
                f"No conditional edge matched action: {state.get('_action')!r}"
            )
        return route

    @staticmethod
    def _matches(edge, state):
        edge_type = edge["edge_type"]
        condition = edge.get("condition") or ""
        action = state.get("_action") or {}
        if edge_type == "ERROR":
            return bool(state.get("metadata", {}).get("runtime_error"))
        if edge_type == "HUMAN_APPROVAL":
            return bool(state.get("metadata", {}).get("human_approved"))
        if condition == "action == 'finish'" or condition == 'action == "finish"':
            return action.get("type") == "finish"
        tool_match = re.fullmatch(
            r"action\.tool\s*==\s*(['\"])([^'\"]+)\1", condition
        )
        if tool_match:
            return action.get("type") == "tool" and action.get("tool") == tool_match.group(2)
        raise ValueError(f"Unsupported LangGraph edge condition: {condition}")
