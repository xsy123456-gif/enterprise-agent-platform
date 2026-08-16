"""Workflow run state (Phase 16.4)."""

from dataclasses import dataclass, field

from app.platform.business.workflow.domain import (
    WF_COMPLETED,
    WF_CREATED,
    WF_FAILED,
    WF_RUNNING,
    WF_WAITING,
    WF_STATUSES,
)


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

    def complete_step(self, step_id):
        self.completed_steps.append(step_id)
        self.current_step = step_id

    def finish(self):
        self.transition(WF_COMPLETED)

    def fail(self):
        self.transition(WF_FAILED)


__all__ = ["WorkflowState"]
