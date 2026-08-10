from app.runtime.contracts import NodeType


class LangGraphDefinitionGenerator:
    """Generate declarative LangGraph backend definitions from Graph IR v1."""

    SCHEMA_VERSION = "langgraph.backend/v1"
    NODE_ADAPTERS = {
        NodeType.AGENT: "AgentNodeAdapter",
        NodeType.TOOL: "ToolNodeAdapter",
        NodeType.MEMORY: "MemoryNodeAdapter",
        NodeType.GOVERNANCE: "GovernanceNodeAdapter",
        NodeType.SUPERVISOR: "SupervisorNodeAdapter",
        NodeType.SUBGRAPH: "SubgraphNodeAdapter",
        NodeType.HUMAN: "HumanNodeAdapter",
    }

    def generate(self, graph_ir):
        nodes = []
        start_nodes = []
        end_nodes = []
        for node in graph_ir.nodes:
            if node.type == NodeType.START:
                start_nodes.append(node.id)
                continue
            if node.type == NodeType.END:
                end_nodes.append(node.id)
                continue
            nodes.append({
                "id": node.id,
                "node_type": node.type.value,
                "adapter": self.NODE_ADAPTERS[node.type],
                "config": dict(node.config),
                "bindings": dict(node.bindings),
                "execution_policy": dict(node.execution_policy),
                "governance": dict(node.governance),
                "retry_policy": dict(node.retry_policy),
                "subgraph_ref": node.subgraph_ref,
            })
        if len(start_nodes) != 1:
            raise ValueError("LangGraph backend requires exactly one START node")
        if not end_nodes:
            raise ValueError("LangGraph backend requires at least one END node")
        return {
            "schema_version": self.SCHEMA_VERSION,
            "graph_ir_schema": graph_ir.schema_version,
            "state_schema": dict(graph_ir.state_schema),
            "execution_policy": dict(graph_ir.execution_policy),
            "start_node": start_nodes[0],
            "end_nodes": end_nodes,
            "nodes": nodes,
            "edges": [edge.to_dict() for edge in graph_ir.edges],
        }
