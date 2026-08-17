"""Multi-agent orchestrator (Phase 14.3).

Drives a collaboration task over an ``AgentTaskGraph``: runs agent tasks in
dependency (topological) order, delegates each to the target agent, and threads
each task's dependency summaries as its input context.
"""

from app.platform.agent_collaboration.domain import AgentDelegationRequest
from app.platform.agent_collaboration.errors import CycleDetectedError


class MultiAgentOrchestrator:

    def __init__(self, delegator):
        self.delegator = delegator

    def execute(self, task, graph):
        order = graph.execution_order()
        if not order:
            raise CycleDetectedError(
                f"agent task graph {graph.task_id!r} contains a cycle"
            )
        results = []
        for node_id in order:
            node = graph.task(node_id)
            request = AgentDelegationRequest(
                delegation_id=f"{task.task_id}:{node_id}",
                task_id=task.task_id,
                from_agent_id=graph.root_agent_id,
                to_agent_id=node.agent_id,
                goal=node.goal,
                input_context_ref=self._context_ref(results, node),
                trace_id=task.request_id,
            )
            result = self.delegator.execute(request)
            results.append((node, result))
        return results

    @staticmethod
    def _context_ref(results, node):
        by_id = {task.task_id: result for task, result in results}
        summaries = [
            by_id[dep].summary for dep in node.dependencies if dep in by_id
        ]
        return "；".join(s for s in summaries if s)


__all__ = ["MultiAgentOrchestrator"]
