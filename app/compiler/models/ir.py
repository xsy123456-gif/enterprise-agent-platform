from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any

from app.runtime.contracts.node import NodeType


class EdgeType(str, Enum):
    NORMAL = "NORMAL"
    CONDITIONAL = "CONDITIONAL"
    ERROR = "ERROR"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"


@dataclass(frozen=True)
class NodeIR:
    id: str
    type: NodeType
    config: dict[str, Any] = field(default_factory=dict)
    bindings: dict[str, Any] = field(default_factory=dict)
    execution_policy: dict[str, Any] = field(default_factory=dict)
    governance: dict[str, Any] = field(default_factory=dict)
    retry_policy: dict[str, Any] = field(default_factory=dict)
    subgraph_ref: str | None = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("NodeIR id is required")
        try:
            object.__setattr__(self, "type", NodeType(self.type))
        except ValueError as error:
            raise ValueError(f"Unsupported NodeIR type: {self.type}") from error
        if self.type == NodeType.SUBGRAPH and not self.subgraph_ref:
            raise ValueError("SUBGRAPH NodeIR requires subgraph_ref")
        if self.type != NodeType.SUBGRAPH and self.subgraph_ref is not None:
            raise ValueError("subgraph_ref is only valid for SUBGRAPH nodes")

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type.value,
            "config": dict(self.config),
            "bindings": dict(self.bindings),
            "execution_policy": dict(self.execution_policy),
            "governance": dict(self.governance),
            "retry_policy": dict(self.retry_policy),
            "subgraph_ref": self.subgraph_ref,
        }

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))


@dataclass(frozen=True)
class EdgeIR:
    source: str
    target: str
    condition: str | None = None
    edge_type: EdgeType = EdgeType.NORMAL

    def __post_init__(self):
        if not self.source or not self.target:
            raise ValueError("EdgeIR source and target are required")
        try:
            object.__setattr__(self, "edge_type", EdgeType(self.edge_type))
        except ValueError as error:
            raise ValueError(f"Unsupported EdgeIR edge_type: {self.edge_type}") from error
        if self.edge_type == EdgeType.CONDITIONAL and not self.condition:
            raise ValueError("Conditional EdgeIR requires a condition")

    def to_dict(self):
        return {
            "source": self.source,
            "target": self.target,
            "condition": self.condition,
            "edge_type": self.edge_type.value,
        }

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))


@dataclass(frozen=True)
class AgentGraphIR:
    agent_id: str
    version: str
    nodes: tuple[NodeIR, ...]
    edges: tuple[EdgeIR, ...]
    state_schema: dict[str, Any]
    bindings: dict[str, Any]
    execution_policy: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"

    def __post_init__(self):
        if not self.agent_id or not self.version:
            raise ValueError("AgentGraphIR agent_id and version are required")
        if self.schema_version != "1.0":
            raise ValueError(f"Unsupported AgentGraphIR schema version: {self.schema_version}")
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
            "execution_policy": dict(self.execution_policy),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        data["nodes"] = tuple(NodeIR.from_dict(item) for item in data.get("nodes", []))
        data["edges"] = tuple(EdgeIR.from_dict(item) for item in data.get("edges", []))
        return cls(**data)

    def canonical_json(self):
        return json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )

    def stable_hash(self):
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
