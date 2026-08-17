"""Agent task graph (Phase 14.2).

A collaboration is modeled as a DAG of ``AgentTask`` nodes (one per delegated
agent) with dependency edges.  ``GraphValidator`` enforces: DAG (no cycles),
max depth, active agents, and allowed delegations.
"""

from dataclasses import dataclass, field

from app.platform.agent_collaboration.errors import (
    CycleDetectedError,
    DelegationDeniedError,
    MaxDepthExceededError,
    AgentUnavailableError,
)


@dataclass(frozen=True)
class AgentTask:
    task_id: str
    agent_id: str
    goal: str = ""
    dependencies: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "dependencies", tuple(self.dependencies or ()))
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.agent_id:
            raise ValueError("agent_id is required")


class AgentTaskGraph:

    def __init__(self, task_id, root_agent_id, tasks):
        self.task_id = task_id
        self.root_agent_id = root_agent_id
        self._tasks = {t.task_id: t for t in tasks}
        for task in tasks:
            for dep in task.dependencies:
                if dep not in self._tasks:
                    raise ValueError(
                        f"task {task.task_id!r} has unknown dependency {dep!r}"
                    )

    def tasks(self):
        return tuple(self._tasks.values())

    def task(self, task_id):
        return self._tasks.get(task_id)

    def dependencies_of(self, task_id):
        return self._tasks[task_id].dependencies

    def execution_order(self):
        """Topological order; returns [] if a cycle exists."""
        indegree = {t.task_id: 0 for t in self._tasks.values()}
        dependents = {t.task_id: [] for t in self._tasks.values()}
        for task in self._tasks.values():
            for dep in task.dependencies:
                indegree[task.task_id] += 1
                dependents[dep].append(task.task_id)
        ready = sorted(tid for tid, deg in indegree.items() if deg == 0)
        order = []
        while ready:
            node = ready.pop(0)
            order.append(node)
            for dependent in dependents[node]:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
        return order if len(order) == len(self._tasks) else []


class GraphValidator:

    def __init__(self, max_agent_depth=3, active_agents=None,
                 allowed_delegations=None):
        self.max_agent_depth = max_agent_depth
        self.active_agents = set(active_agents or ())
        self.allowed_delegations = set(allowed_delegations or ())

    def validate(self, graph: AgentTaskGraph):
        self._check_cycle(graph)
        self._check_depth(graph)
        self._check_agents(graph)
        self._check_delegations(graph)
        return graph

    def _check_cycle(self, graph):
        if not graph.execution_order():
            raise CycleDetectedError(
                f"agent task graph {graph.task_id!r} contains a cycle"
            )

    def _check_depth(self, graph):
        depth = {}

        def compute(task_id):
            if task_id in depth:
                return depth[task_id]
            task = graph.task(task_id)
            d = 1 + max((compute(dep) for dep in task.dependencies), default=0)
            depth[task_id] = d
            return d

        for task in graph.tasks():
            if compute(task.task_id) > self.max_agent_depth:
                raise MaxDepthExceededError(
                    f"task {task.task_id!r} exceeds max depth "
                    f"{self.max_agent_depth}"
                )

    def _check_agents(self, graph):
        if not self.active_agents:
            return
        for task in graph.tasks():
            if task.agent_id not in self.active_agents:
                raise AgentUnavailableError(
                    f"agent {task.agent_id!r} is not active for task "
                    f"{task.task_id!r}"
                )

    def _check_delegations(self, graph):
        if not self.allowed_delegations:
            return
        for task in graph.tasks():
            for dep in task.dependencies:
                dependency = graph.task(dep)
                edge = (dependency.agent_id, task.agent_id)
                if edge not in self.allowed_delegations:
                    raise DelegationDeniedError(
                        f"delegation {edge[0]!r} -> {edge[1]!r} is not allowed"
                    )


__all__ = ["AgentTask", "AgentTaskGraph", "GraphValidator"]
