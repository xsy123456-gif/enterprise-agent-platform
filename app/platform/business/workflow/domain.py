"""Business workflow domain (Phase 16.4)."""

from dataclasses import dataclass, field

STEP_ACTION = "ACTION"
STEP_APPROVAL = "APPROVAL"
STEP_AGENT_TASK = "AGENT_TASK"
STEP_NOTIFICATION = "NOTIFICATION"
STEP_WAIT = "WAIT"
STEP_CONDITION = "CONDITION"
STEP_TYPES = frozenset({
    STEP_ACTION, STEP_APPROVAL, STEP_AGENT_TASK, STEP_NOTIFICATION,
    STEP_WAIT, STEP_CONDITION,
})

WF_CREATED = "CREATED"
WF_RUNNING = "RUNNING"
WF_WAITING = "WAITING"
WF_WAITING_APPROVAL = "WAITING_APPROVAL"
WF_COMPLETED = "COMPLETED"
WF_FAILED = "FAILED"
WF_STATUSES = frozenset({
    WF_CREATED, WF_RUNNING, WF_WAITING, WF_WAITING_APPROVAL, WF_COMPLETED,
    WF_FAILED,
})


@dataclass(frozen=True)
class WorkflowStep:
    step_id: str
    step_type: str
    name: str = ""
    params: dict = field(default_factory=dict)
    next_steps: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "params", dict(self.params or {}))
        object.__setattr__(self, "next_steps", tuple(self.next_steps or ()))
        if not self.step_id:
            raise ValueError("step_id is required")
        if self.step_type not in STEP_TYPES:
            raise ValueError(f"unknown step type: {self.step_type}")

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "step_type": self.step_type,
            "name": self.name,
            "params": dict(self.params),
            "next_steps": list(self.next_steps),
        }


@dataclass(frozen=True)
class BusinessWorkflow:
    workflow_id: str
    version: str
    steps: tuple[WorkflowStep, ...] = ()
    trigger: str = ""
    status: str = WF_CREATED

    def __post_init__(self):
        object.__setattr__(self, "steps", tuple(self.steps or ()))
        if not self.workflow_id:
            raise ValueError("workflow_id is required")
        if not self.version:
            raise ValueError("version is required")
        if self.status not in WF_STATUSES:
            raise ValueError(f"unknown workflow status: {self.status}")

    def step(self, step_id):
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "version": self.version,
            "steps": [s.to_dict() for s in self.steps],
            "trigger": self.trigger,
            "status": self.status,
        }


__all__ = [
    "WorkflowStep",
    "BusinessWorkflow",
    "STEP_TYPES",
    "STEP_ACTION",
    "STEP_APPROVAL",
    "STEP_AGENT_TASK",
    "STEP_NOTIFICATION",
    "STEP_WAIT",
    "STEP_CONDITION",
    "WF_STATUSES",
    "WF_CREATED",
    "WF_RUNNING",
    "WF_WAITING",
    "WF_WAITING_APPROVAL",
    "WF_COMPLETED",
    "WF_FAILED",
]
