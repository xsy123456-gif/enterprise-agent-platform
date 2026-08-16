"""Typed workflow step adapters (Phase 18.5).

Production workflows must run through registered, typed step adapters — never
through arbitrary Python handlers/lambdas.  Each adapter routes its step type
into the correct boundary: ACTION -> BusinessActionRuntime (-> Runtime
Foundation), AGENT_TASK -> the runtime skill-execution adapter, CONDITION -> a
deterministic evaluator (never an LLM), etc.
"""

from abc import ABC, abstractmethod

from app.platform.business.approval.request import (
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
)
from app.platform.business.workflow.domain import (
    STEP_ACTION,
    STEP_AGENT_TASK,
    STEP_APPROVAL,
    STEP_CONDITION,
    STEP_NOTIFICATION,
    STEP_WAIT,
    WF_WAITING,
    WF_WAITING_APPROVAL,
)
from app.platform.business.workflow.state import WorkflowSuspension


def _default_approval_state(step, context):
    return context.get("approval_state", APPROVAL_PENDING)


class WorkflowStepAdapter(ABC):
    step_type: str = ""

    @abstractmethod
    def execute(self, step, context):
        pass


class BusinessActionStepAdapter(WorkflowStepAdapter):
    """ACTION: governed execution through ``BusinessActionRuntime``."""

    step_type = STEP_ACTION

    def __init__(self, action_runtime, action_lookup=None):
        self.action_runtime = action_runtime
        self.action_lookup = action_lookup or (lambda step, ctx: ctx["action"])

    def execute(self, step, context):
        action = self.action_lookup(step, context)
        result = self.action_runtime.execute(action, context)
        return {"result": result.status}


class ApprovalStepAdapter(WorkflowStepAdapter):
    """APPROVAL: human-in-the-loop gate.

    Returns typed outcomes: APPROVED -> completed; PENDING -> suspend
    (WAITING_APPROVAL); REJECTED -> terminal failure.  Pending is a normal
    business wait, never a failure.
    """

    step_type = STEP_APPROVAL

    def __init__(self, approval_lookup=None):
        self.approval_lookup = approval_lookup or _default_approval_state

    def execute(self, step, context):
        state = self.approval_lookup(step, context)
        if state == APPROVAL_APPROVED:
            return {"approved": True}
        if state == APPROVAL_REJECTED:
            from app.platform.business.errors import ApprovalRejectedError
            raise ApprovalRejectedError(
                f"approval step {step.step_id!r} was rejected"
            )
        return WorkflowSuspension(WF_WAITING_APPROVAL, step.step_id)


class AgentTaskStepAdapter(WorkflowStepAdapter):
    """AGENT_TASK: runtime skill/agent execution (Runtime Foundation boundary)."""

    step_type = STEP_AGENT_TASK

    def __init__(self, runner):
        self.runner = runner

    def execute(self, step, context):
        return self.runner(step, context)


class ConditionStepAdapter(WorkflowStepAdapter):
    """CONDITION: deterministic evaluator — never an LLM decision."""

    step_type = STEP_CONDITION

    def __init__(self, evaluator=None):
        self.evaluator = evaluator or (lambda step, ctx: True)

    def execute(self, step, context):
        return {"matches": bool(self.evaluator(step, context))}


class NotificationStepAdapter(WorkflowStepAdapter):
    """NOTIFICATION: notification capability (via ToolRunner in production)."""

    step_type = STEP_NOTIFICATION

    def __init__(self, notifier):
        self.notifier = notifier

    def execute(self, step, context):
        return self.notifier(step, context)


class WaitStepAdapter(WorkflowStepAdapter):
    """WAIT: non-blocking wait signal (never ``time.sleep``).

    Suspends the workflow (WF_WAITING); a resume signal in the context completes
    the step.  The actual pause/resume goes through the runtime boundary, never
    a blocking Python sleep.
    """

    step_type = STEP_WAIT

    def execute(self, step, context):
        if context.get("resume_signal"):
            return {"waited": True}
        return WorkflowSuspension(WF_WAITING, step.step_id)


class LambdaStepAdapter(WorkflowStepAdapter):
    """Test/development convenience: wrap a raw callable as a typed adapter."""

    def __init__(self, step_type, fn):
        self.step_type = step_type
        self._fn = fn

    def execute(self, step, context):
        return self._fn(step, context)


__all__ = [
    "WorkflowStepAdapter",
    "BusinessActionStepAdapter",
    "ApprovalStepAdapter",
    "AgentTaskStepAdapter",
    "ConditionStepAdapter",
    "NotificationStepAdapter",
    "WaitStepAdapter",
    "LambdaStepAdapter",
]
