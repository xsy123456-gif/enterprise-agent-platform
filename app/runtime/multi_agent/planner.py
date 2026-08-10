"""Deterministic DAG-to-plan preparation; no Agent execution occurs here."""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from app.runtime.multi_agent.models import AgentTask, AgentTaskStatus


def utc_now():
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class AgentGraphExecutionPlan:
    execution_id: str
    graph_id: str
    nodes: tuple[AgentTask, ...]
    dependencies: dict[str, tuple[str, ...]]
    parallel_groups: tuple[tuple[str, ...], ...]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(
            self, "dependencies",
            {str(key): tuple(value) for key, value in self.dependencies.items()},
        )
        object.__setattr__(self, "parallel_groups", tuple(
            tuple(group) for group in self.parallel_groups
        ))
        if not self.execution_id or not self.graph_id:
            raise ValueError("execution_id and graph_id are required")
        if len({task.task_id for task in self.nodes}) != len(self.nodes):
            raise ValueError("Execution plan task IDs must be unique")

    def task(self, task_id):
        return next(task for task in self.nodes if task.task_id == task_id)

    def to_dict(self):
        return {
            "execution_id": self.execution_id,
            "graph_id": self.graph_id,
            "nodes": [task.to_dict() for task in self.nodes],
            "dependencies": {
                key: list(value) for key, value in self.dependencies.items()
            },
            "parallel_groups": [list(group) for group in self.parallel_groups],
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        data["nodes"] = tuple(AgentTask.from_dict(item) for item in data["nodes"])
        restored_nodes = []
        for task in data["nodes"]:
            context = task.input_context
            if isinstance(context, dict) and context.get("schema_version") == "agent-context.v1":
                from app.runtime.multi_agent.context import AgentContextEnvelope
                task = replace(
                    task, input_context=AgentContextEnvelope.from_dict(context)
                )
            restored_nodes.append(task)
        data["nodes"] = tuple(restored_nodes)
        data["dependencies"] = {
            key: tuple(value) for key, value in data["dependencies"].items()
        }
        data["parallel_groups"] = tuple(
            tuple(group) for group in data["parallel_groups"]
        )
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


class AgentGraphPlanner:
    """Builds a deterministic dependency plan from an execution graph."""

    def build(self, graph, initial_context=None):
        node_ids = [node.agent_id for node in graph.nodes]
        dependencies = {node_id: [] for node_id in node_ids}
        for edge in graph.edges:
            if edge.target in dependencies and edge.source != graph.root_agent:
                dependencies[edge.target].append(edge.source)
        dependencies = {
            node_id: tuple(sorted(values))
            for node_id, values in dependencies.items()
        }
        groups = self._parallel_groups(node_ids, dependencies)
        tasks = tuple(
            AgentTask(
                task_id=f"{graph.execution_id}:{node_id}",
                agent_id=node_id,
                artifact_hash=graph.get_node(node_id).artifact_hash,
                dependencies=tuple(
                    f"{graph.execution_id}:{dependency}"
                    for dependency in dependencies[node_id]
                ),
                input_context=initial_context,
            )
            for node_id in node_ids
        )
        return AgentGraphExecutionPlan(
            execution_id=graph.execution_id,
            graph_id=graph.graph_id,
            nodes=tasks,
            dependencies={
                f"{graph.execution_id}:{node_id}": tuple(
                    f"{graph.execution_id}:{dependency}"
                    for dependency in values
                )
                for node_id, values in dependencies.items()
            },
            parallel_groups=tuple(
                tuple(f"{graph.execution_id}:{node_id}" for node_id in group)
                for group in groups
            ),
        )

    @staticmethod
    def _parallel_groups(node_ids, dependencies):
        remaining = set(node_ids)
        completed = set()
        groups = []
        while remaining:
            ready = tuple(
                node_id for node_id in node_ids
                if node_id in remaining
                and set(dependencies[node_id]).issubset(completed)
            )
            if not ready:
                raise ValueError("Execution graph contains a dependency cycle")
            groups.append(ready)
            remaining.difference_update(ready)
            completed.update(ready)
        return groups
