from app.compiler.models.ir import AgentGraphIR, EdgeIR, NodeIR, NodeType


class AgentGraphIRBuilder:
    """Builds runtime-neutral IR; it never constructs executable graph objects."""

    STATE_SCHEMA = {
        "task": "str",
        "messages": "list[message]",
        "tool_results": "list[object]",
        "trace_id": "str",
        "execution_context": "dict",
    }

    def build(self, compile_input):
        definition = compile_input.agent_definition
        nodes = [
            NodeIR("start", NodeType.START),
            NodeIR(
                "governance", NodeType.GOVERNANCE,
                bindings={"policy_ref": definition.policy_ref},
            ),
        ]
        edges = [EdgeIR("start", "governance")]
        previous = "governance"

        if definition.memory_read or definition.memory_write:
            nodes.append(NodeIR(
                "memory", NodeType.MEMORY,
                config={
                    "read_types": list(definition.memory_read),
                    "write_types": list(definition.memory_write),
                },
            ))
            edges.append(EdgeIR(previous, "memory"))
            previous = "memory"

        nodes.append(NodeIR(
            "agent", NodeType.AGENT,
            config={"runtime": dict(definition.runtime)},
            bindings={
                "agent_id": definition.agent_id,
                "version": definition.version,
                "capabilities": list(definition.capabilities),
            },
        ))
        edges.append(EdgeIR(previous, "agent"))

        for tool_name in definition.allowed_tools:
            node_id = f"tool:{tool_name}"
            nodes.append(NodeIR(
                node_id, NodeType.TOOL, bindings={"tool_name": tool_name},
            ))
            edges.append(EdgeIR(
                "agent", node_id, condition=f"action.tool == '{tool_name}'",
                edge_type="conditional",
            ))
            edges.append(EdgeIR(node_id, "agent"))

        nodes.append(NodeIR("end", NodeType.END))
        edges.append(EdgeIR(
            "agent", "end", condition="action == 'finish'", edge_type="conditional"
        ))
        return AgentGraphIR(
            agent_id=definition.agent_id,
            version=definition.version,
            nodes=tuple(nodes),
            edges=tuple(edges),
            state_schema=dict(self.STATE_SCHEMA),
            bindings={
                "compiler_version": compile_input.compiler_version,
                "policy_ref": definition.policy_ref,
                "capabilities": list(definition.capabilities),
                "tools": list(definition.allowed_tools),
            },
        )
