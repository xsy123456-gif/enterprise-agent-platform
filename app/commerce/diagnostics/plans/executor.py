"""Deterministic Plan Executor.

Executes a compiled ``PlanIR`` over its typed step handlers in topological DAG
order.  WHEN conditions gate step execution; each step has a failure policy
(SKIP / MARK_UNKNOWN / STOP); RESULT_ASSEMBLE (or an early DATA_QUALITY_GATE)
sets the plan outcome (STOP_SUCCESS / STOP_NORMAL / STOP_INSUFFICIENT_DATA /
STOP_UNSUPPORTED).
"""

import uuid

from app.commerce.diagnostics.plans.handlers import HANDLERS
from app.commerce.diagnostics.plans.schema import (
    FAILURE_MARK_UNKNOWN,
    FAILURE_SKIP,
    FAILURE_STOP,
    STEP_STATUS_FAILED,
    STEP_STATUS_MARKED_UNKNOWN,
    STEP_STATUS_SKIPPED,
    STEP_STATUS_SUCCEEDED,
    STOP_UNSUPPORTED,
)
from app.commerce.diagnostics.plans.state import PlanExecutionState
from app.commerce.diagnostics.plans.when import evaluate_all


class PlanContext:
    """Execution context: pinned-definition resolution + fact executor."""

    def __init__(self, compile_context, fact_executor):
        self.compile_context = compile_context
        self.fact_executor = fact_executor
        self.plan_ir = None

    def resolve(self, ref):
        registry = self.compile_context.registry_for(ref.kind)
        return registry.get(ref.id, ref.version)


class PlanExecutionError(Exception):
    pass


class PlanExecutor:

    def execute(self, ir, compile_context, fact_executor, subject, execution_id=None):
        state = PlanExecutionState(
            plan_id=ir.plan_id,
            plan_version=ir.version,
            checksum=ir.checksum,
            execution_id=execution_id or uuid.uuid4().hex,
            subject=subject,
        )
        context = PlanContext(compile_context, fact_executor)
        context.plan_ir = ir
        for step in self._topological_order(ir):
            if state._terminated:
                break
            if not evaluate_all(step.when, state):
                state.mark(step.step_id, STEP_STATUS_SKIPPED)
                continue
            handler = HANDLERS[step.type]
            try:
                handler(step, state, context)
                state.mark(step.step_id, STEP_STATUS_SUCCEEDED)
                if state._terminated:
                    break
            except Exception as error:  # noqa: BLE001 - failure policy dispatch
                state.errors.append(f"{step.step_id}: {error}")
                if step.on_failure == FAILURE_STOP:
                    state.mark(step.step_id, STEP_STATUS_FAILED, str(error))
                    state.outcome = STOP_UNSUPPORTED
                    break
                if step.on_failure == FAILURE_MARK_UNKNOWN:
                    state.mark(step.step_id, STEP_STATUS_MARKED_UNKNOWN, str(error))
                else:  # SKIP
                    state.mark(step.step_id, STEP_STATUS_SKIPPED, str(error))
        return state

    @staticmethod
    def _topological_order(ir):
        steps = {step.step_id: step for step in ir.steps}
        order_index = {step.step_id: i for i, step in enumerate(ir.steps)}
        indegree = {step_id: 0 for step_id in steps}
        for step in ir.steps:
            for nxt in step.next:
                indegree[nxt] += 1
        queue = [sid for sid in indegree if indegree[sid] == 0]
        ordered = []
        while queue:
            queue.sort(key=lambda sid: order_index[sid])
            sid = queue.pop(0)
            ordered.append(steps[sid])
            for nxt in steps[sid].next:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)
        if len(ordered) != len(steps):
            raise PlanExecutionError("plan graph is not acyclic")
        return ordered


__all__ = ["PlanExecutor", "PlanContext", "PlanExecutionError"]
