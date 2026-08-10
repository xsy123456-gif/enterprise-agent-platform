"""Ports for executing Supervisor-owned Agent graphs.

No scheduler or backend implementation belongs to Group 1.  These ports make
the ownership boundary explicit without introducing a second Runtime.
"""

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

from app.runtime.multi_agent.contracts import (
    AgentExecutionResult,
    AgentInvocationRequest,
)
from app.runtime.multi_agent.aggregator import AgentResultAggregator
from app.runtime.multi_agent.graph import AgentExecutionGraph
from app.runtime.multi_agent.mapping import AgentResultMapper
from app.runtime.multi_agent.models import AgentNode, AgentTaskStatus
from app.runtime.multi_agent.scheduler import AgentGraphScheduler
from app.runtime.multi_agent.policies import GraphExecutionPolicy


class AgentRuntimeInvoker(ABC):
    """Supervisor-side port; implementations must delegate to GraphRuntime."""

    @abstractmethod
    def invoke(
        self,
        node: AgentNode,
        request: AgentInvocationRequest,
    ) -> AgentExecutionResult:
        pass


class SupervisorGraphRuntime(ABC):
    """Owns graph orchestration while Agent Runtimes remain isolated units."""

    @abstractmethod
    def execute(
        self,
        graph: AgentExecutionGraph,
        invocations: tuple[AgentInvocationRequest, ...],
    ) -> tuple[AgentExecutionResult, ...]:
        pass


class ParallelGraphExecutor(SupervisorGraphRuntime):
    """Parent-runtime executor with bounded fan-out/fan-in semantics.

    This is an in-process execution implementation of the port. It is not a
    queue, worker service, retry engine, or Agent-to-Agent invocation path.
    """

    def __init__(self, invoker, scheduler=None, aggregator=None, max_workers=None,
                 result_mapper=None, policy=None):
        if not isinstance(invoker, AgentRuntimeInvoker):
            raise TypeError("invoker must implement AgentRuntimeInvoker")
        self.invoker = invoker
        self.scheduler = scheduler or AgentGraphScheduler()
        self.aggregator = aggregator or AgentResultAggregator()
        self.max_workers = max_workers
        self.policy = policy or GraphExecutionPolicy(max_parallelism=max_workers)
        self.result_mapper = result_mapper or AgentResultMapper()
        self.last_plan = None
        self.last_skipped_agents = ()

    def execute(self, graph, invocations):
        plan = self.scheduler.create_plan(graph)
        self.last_plan = plan
        requests = {request.target_agent: request for request in invocations}
        for request in requests.values():
            if request.execution_id != graph.execution_id:
                raise ValueError("Invocation execution_id does not match graph")
        tasks = {task.task_id: task for task in plan.nodes}
        results = []
        failed_task_ids = set()
        skipped_agents = []
        for group in plan.parallel_groups:
            runnable = []
            for task_id in group:
                task = tasks[task_id]
                if not self.scheduler.dependencies_satisfied(
                    task, {
                        item.task_id for item in tasks.values()
                        if item.status is AgentTaskStatus.COMPLETED
                    }
                ) or any(dependency in failed_task_ids for dependency in task.dependencies):
                    tasks[task_id] = task.transition(AgentTaskStatus.SKIPPED)
                    skipped_agents.append(task.agent_id)
                    continue
                request = requests.get(task.agent_id)
                if request is None:
                    raise ValueError(f"Missing invocation for Agent: {task.agent_id}")
                tasks[task_id] = task.transition(AgentTaskStatus.READY)
                runnable.append((task_id, task, request, graph.get_node(task.agent_id)))
            if not runnable:
                continue
            for task_id, task, request, node in runnable:
                tasks[task_id] = tasks[task_id].transition(AgentTaskStatus.RUNNING)
            worker_count = self.policy.max_parallelism or self.max_workers or len(runnable)
            with ThreadPoolExecutor(max_workers=min(worker_count, len(runnable))) as pool:
                futures = {
                    pool.submit(self._invoke, request, node): (task_id, task)
                    for task_id, task, request, node in runnable
                }
                batch = []
                for future, (task_id, task) in futures.items():
                    result = future.result()
                    batch.append((task_id, task, result))
            for task_id, task, result in batch:
                results.append(result)
                if result.status.value in {"failed", "denied", "cancelled"}:
                    tasks[task_id] = tasks[task_id].transition(
                        AgentTaskStatus.FAILED, result=result
                    )
                    failed_task_ids.add(task_id)
                else:
                    tasks[task_id] = tasks[task_id].transition(
                        AgentTaskStatus.COMPLETED, result=result
                    )
        self.last_skipped_agents = tuple(skipped_agents)
        return tuple(results)

    def execute_aggregated(self, graph, invocations):
        results = self.execute(graph, invocations)
        return self.aggregator.aggregate(
            graph.execution_id, results, skipped_agents=self.last_skipped_agents
        )

    def _invoke(self, request, node):
        try:
            result = self.invoker.invoke(node, request)
            if not isinstance(result, AgentExecutionResult):
                raise TypeError("AgentRuntimeInvoker must return AgentExecutionResult")
            return result
        except Exception as error:
            return self.result_mapper.map_error(error, request, node)
