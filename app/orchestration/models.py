from dataclasses import dataclass, field
from typing import Any, Optional


class StepStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SUCCESS = COMPLETED
    FAILED = "failed"
    BLOCKED = "blocked"

    ALL = {PENDING, RUNNING, COMPLETED, FAILED, BLOCKED}
    TERMINAL = {COMPLETED, FAILED, BLOCKED}


class ExecutionStatus:
    PENDING = "pending"
    CREATED = PENDING
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"

    ALL = {PENDING, RUNNING, COMPLETED, FAILED, BLOCKED}


@dataclass
class StepResult:
    step_id: str
    capability: str
    status: str
    agent_id: Optional[str] = None
    agent_version: Optional[str] = None
    output: Any = None
    result_ref: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self):
        return {
            "step_id": self.step_id,
            "capability": self.capability,
            "status": self.status,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "output": self.output,
            "result_ref": self.result_ref,
            "error": self.error,
        }


@dataclass
class SupervisionResult:
    execution_id: str
    task_id: str
    status: str
    output: Any = None
    steps: list[StepResult] = field(default_factory=list)
    replan_required: bool = False
    execution_context: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "execution_id": self.execution_id,
            "task_id": self.task_id,
            "status": self.status,
            "output": self.output,
            "steps": [step.to_dict() for step in self.steps],
            "replan_required": self.replan_required,
            "execution_context": self.execution_context,
        }
