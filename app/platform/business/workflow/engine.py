"""Workflow engine (Phase 16.4 + 18.5 + 18.5.1).

Executes a ``BusinessWorkflow`` (a DAG of steps) in dependency order, delegating
each step to a registered typed adapter.  It reuses the Runtime Foundation — it
never re-implements an execution engine and never performs business judgment
itself.

Phase 18.5.1: steps may return a ``WorkflowSuspension`` (or raise
``ApprovalRequiredError`` for compatibility) to *pause* — the run enters
WAITING / WAITING_APPROVAL and every downstream node stops.  ``resume``
continues from the suspended step.
"""

import uuid
from dataclasses import dataclass, field

from app.platform.business.errors import (
    ApprovalRejectedError,
    ApprovalRequiredError,
    WorkflowError,
)
from app.platform.business.workflow.domain import (
    WF_WAITING,
    WF_WAITING_APPROVAL,
    BusinessWorkflow,
)
from app.platform.business.workflow.run_repository import (
    InMemoryWorkflowRunRepository,
    WorkflowRunRepository,
)
from app.platform.business.workflow.state import WorkflowState, WorkflowSuspension


def _execution_order(steps):
    indegree = {s.step_id: 0 for s in steps}
    successors = {s.step_id: [] for s in steps}
    for step in steps:
        for nxt in step.next_steps:
            indegree[nxt] += 1
            successors[step.step_id].append(nxt)
    ready = sorted(sid for sid, deg in indegree.items() if deg == 0)
    order = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for nxt in successors[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
    return order if len(order) == len(steps) else []


@dataclass
class WorkflowRun:
    run_id: str
    workflow: BusinessWorkflow
    state: WorkflowState
    order: list
    cursor: int = 0
    step_results: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)

    @property
    def status(self):
        return self.state.status

    @property
    def current_step_id(self):
        return self.order[self.cursor] if self.cursor < len(self.order) else ""

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "workflow_id": self.workflow.workflow_id,
            "status": self.status,
            "step_results": dict(self.step_results),
            "current_step": self.current_step_id,
        }


class WorkflowEngine:

    def __init__(self, step_handlers=None, step_adapters=None, strict=False,
                 run_repository=None):
        if strict and step_handlers:
            raise WorkflowError(
                "production workflow engine must not use arbitrary step handlers"
            )
        self._handlers = dict(step_handlers or {})
        for adapter in (step_adapters or []):
            self._handlers.setdefault(adapter.step_type, adapter.execute)
        self.run_repository = run_repository or InMemoryWorkflowRunRepository()

    def run(self, workflow: BusinessWorkflow, context=None) -> WorkflowRun:
        order = _execution_order(workflow.steps)
        if not order:
            raise WorkflowError(
                f"workflow {workflow.workflow_id!r} has a cycle or unknown edge"
            )
        state = WorkflowState(workflow_id=workflow.workflow_id)
        state.mark_running()
        run = WorkflowRun(
            run_id=uuid.uuid4().hex, workflow=workflow, state=state,
            order=order, context=dict(context or {}),
        )
        self.run_repository.save(run)
        return self._execute(run)

    def resume(self, run_id, context_update=None) -> WorkflowRun:
        run = self.run_repository.get(run_id)
        if run is None:
            raise WorkflowError(f"unknown workflow run {run_id!r}")
        if run.status not in (WF_WAITING, WF_WAITING_APPROVAL):
            raise WorkflowError(
                f"workflow {run_id!r} is not resumable (status {run.status!r})"
            )
        if context_update:
            run.context.update(context_update)
        run.state.mark_running()
        return self._execute(run)

    def _execute(self, run: WorkflowRun) -> WorkflowRun:
        while run.cursor < len(run.order):
            step_id = run.order[run.cursor]
            step = run.workflow.step(step_id)
            handler = self._handlers.get(step.step_type)
            if handler is None:
                raise WorkflowError(
                    f"no handler for step type {step.step_type!r}"
                )
            try:
                result = handler(step, run.context)
            except ApprovalRequiredError:
                run.state.mark_waiting_approval(step_id)
                self.run_repository.save(run)
                return run
            except ApprovalRejectedError:
                run.state.fail()
                self.run_repository.save(run)
                return run
            except Exception:  # noqa: BLE001 - surfaced as FAILED
                run.state.fail()
                self.run_repository.save(run)
                return run
            if isinstance(result, WorkflowSuspension):
                run.state.mark_waiting_by_type(result.suspension_type, step_id)
                self.run_repository.save(run)
                return run
            run.step_results[step_id] = result
            run.state.complete_step(step_id)
            run.cursor += 1
        run.state.finish()
        self.run_repository.save(run)
        return run


__all__ = ["WorkflowEngine", "WorkflowRun", "WorkflowRunRepository",
           "InMemoryWorkflowRunRepository"]
