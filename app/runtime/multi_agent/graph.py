"""Validated Multi-Agent execution graph contract."""

from dataclasses import dataclass

from app.runtime.multi_agent.models import (
    AgentExecutionGraphStatus,
    AgentGraphEdge,
    AgentNode,
)


@dataclass(frozen=True)
class AgentExecutionGraph:
    """A plan owned by a Supervisor; it does not execute or schedule Agents."""

    graph_id: str
    execution_id: str
    root_agent: str
    nodes: tuple[AgentNode, ...]
    edges: tuple[AgentGraphEdge, ...] = ()
    status: AgentExecutionGraphStatus = AgentExecutionGraphStatus.CREATED

    def __post_init__(self):
        for name in ("graph_id", "execution_id", "root_agent"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "edges", tuple(self.edges))
        object.__setattr__(self, "status", AgentExecutionGraphStatus(self.status))
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("AgentExecutionGraph Agent IDs must be unique")
        known = set(node_ids) | {self.root_agent}
        unknown = {
            endpoint
            for edge in self.edges
            for endpoint in (edge.source, edge.target)
            if endpoint not in known
        }
        if unknown:
            raise ValueError(
                "AgentExecutionGraph edges reference unknown Agents: "
                f"{sorted(unknown)}"
            )
        self._validate_acyclic(known)

    def get_node(self, agent_id):
        for node in self.nodes:
            if node.agent_id == agent_id:
                return node
        raise KeyError(f"Agent node not found: {agent_id}")

    def to_dict(self):
        return {
            "graph_id": self.graph_id,
            "execution_id": self.execution_id,
            "root_agent": self.root_agent,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        data["nodes"] = tuple(
            AgentNode.from_dict(item) for item in data.get("nodes", [])
        )
        data["edges"] = tuple(
            AgentGraphEdge.from_dict(item) for item in data.get("edges", [])
        )
        return cls(**data)

    def _validate_acyclic(self, known):
        adjacency = {node_id: [] for node_id in known}
        indegree = {node_id: 0 for node_id in known}
        for edge in self.edges:
            adjacency[edge.source].append(edge.target)
            indegree[edge.target] += 1
        ready = [node_id for node_id, degree in indegree.items() if degree == 0]
        visited = 0
        while ready:
            current = ready.pop()
            visited += 1
            for target in adjacency[current]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
        if visited != len(known):
            raise ValueError("AgentExecutionGraph must be acyclic")
