from abc import ABC, abstractmethod

from app.orchestration.plan import TaskPlan
from app.orchestration.task import TaskStep


class PlanningError(Exception):
    pass


class Planner(ABC):
    """Transforms a user task into capability-based work."""

    @abstractmethod
    def plan(self, task):
        pass


class BasicPlanner(Planner):
    """A deterministic fallback plan for tests and LLM outages."""

    def __init__(self, fallback_steps=None):
        self.fallback_steps = fallback_steps or [
            TaskStep(step_id="1", capability="customer_analysis"),
            TaskStep(
                step_id="2",
                capability="visit_prepare",
                dependencies=["1"],
            ),
        ]

    def plan(self, task):
        query = task.user_query.strip()
        if not query:
            raise PlanningError("user_query is required")

        # The fallback is deliberately configured, rather than inferred from
        # business keywords. Cognitive mapping belongs to LLMPlanner.
        steps = [
            TaskStep(
                step_id=step.step_id,
                capability=step.capability,
                dependencies=list(step.dependencies),
                context=dict(step.context),
            )
            for step in self.fallback_steps
        ]
        context = dict(task.context)
        context["user_query"] = query

        return TaskPlan(
            task_id=task.task_id,
            goal=query,
            steps=steps,
            context=context,
        )
