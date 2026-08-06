from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Any, Optional
import uuid

from app.orchestration.models import ExecutionStatus, StepStatus
from app.orchestration.task import utc_now


@dataclass
class ExecutionStepState:
    step_id: str
    status: str = StepStatus.PENDING
    agent_id: Optional[str] = None
    agent_version: Optional[str] = None
    result: Any = None
    result_ref: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self):
        return {
            "step_id": self.step_id,
            "status": self.status,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "result": self.result,
            "result_ref": self.result_ref,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class ExecutionState:
    task_id: str
    steps: list[ExecutionStepState]
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = ExecutionStatus.PENDING
    current_step: Optional[str] = None
    running_steps: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def from_plan(cls, plan):
        return cls(
            task_id=plan.task_id,
            steps=[ExecutionStepState(step_id=step.step_id) for step in plan.steps],
        )

    def get_step(self, step_id):
        for step in self.steps:
            if step.step_id == step_id:
                return step
        raise KeyError(f"Execution step not found: {step_id}")

    def start(self):
        self.status = ExecutionStatus.RUNNING
        self.updated_at = utc_now()

    def start_step(self, step_id, agent_id, agent_version):
        step = self.get_step(step_id)
        self._require_status(step, StepStatus.PENDING)
        step.status = StepStatus.RUNNING
        step.agent_id = agent_id
        step.agent_version = agent_version
        step.started_at = utc_now()
        self.running_steps.append(step_id)
        self.current_step = self.running_steps[0]
        self.updated_at = step.started_at

    def complete_step(self, step_id, result):
        step = self.get_step(step_id)
        self._require_status(step, StepStatus.RUNNING)
        step.status = StepStatus.COMPLETED
        step.result = result
        step.result_ref = f"{self.execution_id}:{step_id}"
        step.completed_at = utc_now()
        self._finish_running_step(step_id)
        self.updated_at = step.completed_at

    def fail_step(self, step_id, error):
        step = self.get_step(step_id)
        self._require_status(step, StepStatus.RUNNING)
        step.status = StepStatus.FAILED
        step.error = str(error)
        step.completed_at = utc_now()
        self._finish_running_step(step_id)
        self.status = ExecutionStatus.FAILED
        self.updated_at = step.completed_at

    def block_step(self, step_id, error):
        step = self.get_step(step_id)
        self._require_status(step, StepStatus.PENDING)
        step.status = StepStatus.BLOCKED
        step.error = str(error)
        step.completed_at = utc_now()
        if self.status != ExecutionStatus.FAILED:
            self.status = ExecutionStatus.BLOCKED
        self.updated_at = step.completed_at

    def complete(self):
        self.status = ExecutionStatus.COMPLETED
        self.current_step = None
        self.running_steps = []
        self.updated_at = utc_now()

    def to_dict(self):
        return {
            "execution_id": self.execution_id,
            "task_id": self.task_id,
            "current_step": self.current_step,
            "running_steps": list(self.running_steps),
            "status": self.status,
            "steps": [step.to_dict() for step in self.steps],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def _require_status(step, expected):
        if step.status != expected:
            raise RuntimeError(
                f"Step {step.step_id} must be {expected}, got {step.status}"
            )

    def _finish_running_step(self, step_id):
        if step_id in self.running_steps:
            self.running_steps.remove(step_id)
        self.current_step = self.running_steps[0] if self.running_steps else None


class ExecutionStateStore(ABC):
    @abstractmethod
    def save(self, state):
        pass

    @abstractmethod
    def get(self, execution_id):
        pass


class InMemoryExecutionStateStore(ExecutionStateStore):
    def __init__(self):
        self._states = {}

    def save(self, state):
        self._states[state.execution_id] = state
        return state

    def get(self, execution_id):
        return self._states.get(execution_id)
