from dataclasses import dataclass, field
from typing import Any

from app.orchestration.task import TaskStep, utc_now


@dataclass
class TaskPlan:
    task_id: str
    goal: str
    steps: list[TaskStep]
    context: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.goal:
            raise ValueError("goal is required")
        if not self.steps:
            raise ValueError("A task plan requires at least one step")

        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Task step IDs must be unique")

        known_steps = set(step_ids)
        for step in self.steps:
            unknown = set(step.dependencies) - known_steps
            if unknown:
                raise ValueError(
                    f"Unknown dependencies for step {step.step_id}: "
                    f"{sorted(unknown)}"
                )

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "steps": [step.to_dict() for step in self.steps],
            "context": dict(self.context),
            "created_at": self.created_at,
        }
