"""Pure DAG planning utilities, not a queue or worker scheduler service."""

from app.runtime.multi_agent.planner import AgentGraphExecutionPlan, AgentGraphPlanner


class AgentGraphScheduler:
    """Compatibility name for graph planning owned by the Parent Runtime."""

    def __init__(self, planner=None):
        self.planner = planner or AgentGraphPlanner()

    def create_plan(self, graph, initial_context=None) -> AgentGraphExecutionPlan:
        return self.planner.build(graph, initial_context=initial_context)

    @staticmethod
    def dependencies_satisfied(task, completed_task_ids):
        return set(task.dependencies).issubset(set(completed_task_ids))
