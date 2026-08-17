"""Workflow run state + suspension signal (Phase 16.4 / 18.5.1)."""

from dataclasses import dataclass, field

from app.platform.business.workflow.domain import (
    WF_COMPLETED,
    WF_CREATED,
    WF_FAILED,
    WF_RUNNING,
    WF_WAITING,
    WF_WAITING_APPROVAL,
    WF_STATUSES,
)


@dataclass(frozen=True)
class WorkflowSuspension:
    """A typed *return value* (not an exception) signalling a normal pause.

    ``suspension_type`` is ``WF_WAITING`` or ``WF_WAITING_APPROVAL``.  A step
    returns this when it must stop the DAG until an external signal (approval /
    wait) resumes it.
    """

    suspension_type: str
    step_id: str

    def __post_init__(self):
        if self.suspension_type not in (WF_WAITING, WF_WAITING_APPROVAL):
            raise ValueError(f"unknown suspension type: {self.suspension_type}")


@dataclass
class WorkflowState:
    workflow_id: str
    status: str = WF_CREATED
    completed_steps: list = field(default_factory=list)
    current_step: str = ""

    def transition(self, status):
        if status not in WF_STATUSES:
            raise ValueError(f"unknown workflow status: {status}")
        self.status = status

    def mark_running(self):
        self.transition(WF_RUNNING)

    def mark_waiting(self, step_id):
        self.current_step = step_id
        self.transition(WF_WAITING)

    def mark_waiting_approval(self, step_id):
        self.current_step = step_id
        self.transition(WF_WAITING_APPROVAL)

    def mark_waiting_by_type(self, suspension_type, step_id):
        if suspension_type == WF_WAITING_APPROVAL:
            self.mark_waiting_approval(step_id)
        else:
            self.mark_waiting(step_id)

    def complete_step(self, step_id):
        self.completed_steps.append(step_id)
        self.current_step = step_id

    def finish(self):
        self.transition(WF_COMPLETED)

    def fail(self):
        self.transition(WF_FAILED)


__all__ = ["WorkflowState", "WorkflowSuspension"]
