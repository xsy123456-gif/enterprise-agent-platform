"""Workflow engine (Phase 16.4).

Executes a ``BusinessWorkflow`` (a DAG of steps) in dependency order, delegating
each step to an injected handler.  It reuses the Runtime Foundation — it never
re-implements an execution engine and never performs business judgment itself.
"""

from dataclasses import dataclass, field

from app.platform.business.errors import WorkflowError
from app.platform.business.workflow.state import WorkflowState


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
class WorkflowRunResult:
    workflow_id: str
    status: str = "COMPLETED"
    step_results: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "status": self.status,
            "step_results": dict(self.step_results),
        }


class WorkflowEngine:

    def __init__(self, step_handlers=None):
        self.step_handlers = dict(step_handlers or {})

    def run(self, workflow, context=None) -> WorkflowRunResult:
        order = _execution_order(workflow.steps)
        if not order:
            raise WorkflowError(
                f"workflow {workflow.workflow_id!r} has a cycle or unknown edge"
            )
        state = WorkflowState(workflow_id=workflow.workflow_id)
        state.mark_running()
        step_results = {}
        for step_id in order:
            step = workflow.step(step_id)
            handler = self.step_handlers.get(step.step_type)
            if handler is None:
                raise WorkflowError(
                    f"no handler for step type {step.step_type!r}"
                )
            try:
                result = handler(step, context)
                step_results[step_id] = result
                state.complete_step(step_id)
            except Exception as error:  # noqa: BLE001 - surfaced as FAILED
                state.fail()
                return WorkflowRunResult(
                    workflow_id=workflow.workflow_id, status="FAILED",
                    step_results=step_results)
        state.finish()
        return WorkflowRunResult(
            workflow_id=workflow.workflow_id, status=state.status,
            step_results=step_results)


__all__ = ["WorkflowEngine", "WorkflowRunResult"]
