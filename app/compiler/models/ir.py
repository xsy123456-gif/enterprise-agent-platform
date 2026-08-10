from dataclasses import dataclass, field
from typing import Any


class NodeType:
    START = "START"
    END = "END"
    AGENT = "AGENT"
    TOOL = "TOOL"
    MEMORY = "MEMORY"
    GOVERNANCE = "GOVERNANCE"
    SUPERVISOR = "SUPERVISOR"
    SUBGRAPH = "SUBGRAPH"
    HUMAN = "HUMAN"

    ALL = {
        START, END, AGENT, TOOL, MEMORY, GOVERNANCE, SUPERVISOR, SUBGRAPH, HUMAN,
    }


@dataclass(frozen=True)
class NodeIR:
    id: str
    type: str
    config: dict[str, Any] = field(default_factory=dict)
    bindings: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            raise ValueError("NodeIR id is required")
        if self.type not in NodeType.ALL:
            raise ValueError(f"Unsupported NodeIR type: {self.type}")

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "config": dict(self.config),
            "bindings": dict(self.bindings),
        }


@dataclass(frozen=True)
class EdgeIR:
    source: str
    target: str
    condition: str | None = None
    edge_type: str = "normal"

    def __post_init__(self):
        if not self.source or not self.target:
            raise ValueError("EdgeIR source and target are required")
        if self.edge_type not in {"normal", "conditional", "exception"}:
            raise ValueError(f"Unsupported EdgeIR edge_type: {self.edge_type}")
        if self.edge_type == "conditional" and not self.condition:
            raise ValueError("Conditional EdgeIR requires a condition")

    def to_dict(self):
        return {
            "source": self.source,
            "target": self.target,
            "condition": self.condition,
            "edge_type": self.edge_type,
        }


@dataclass(frozen=True)
class AgentGraphIR:
    agent_id: str
    version: str
    nodes: tuple[NodeIR, ...]
    edges: tuple[EdgeIR, ...]
    state_schema: dict[str, Any]
    bindings: dict[str, Any]

    def __post_init__(self):
        if not self.agent_id or not self.version:
            raise ValueError("AgentGraphIR agent_id and version are required")
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("AgentGraphIR node IDs must be unique")
        unknown = {
            endpoint
            for edge in self.edges
            for endpoint in (edge.source, edge.target)
            if endpoint not in set(ids)
        }
        if unknown:
            raise ValueError(f"AgentGraphIR edges reference unknown nodes: {sorted(unknown)}")

    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "state_schema": dict(self.state_schema),
            "bindings": dict(self.bindings),
        }
