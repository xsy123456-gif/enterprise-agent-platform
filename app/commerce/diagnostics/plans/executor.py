"""Deterministic Plan Executor.

Executes a compiled ``PlanIR`` by following its ``next`` DAG edges from the
entry step: only *reachable* steps whose WHEN conditions are satisfied execute.
Steps have a failure policy (SKIP / MARK_UNKNOWN / STOP); a max-depth violation
is a hard typed failure.  RESULT_ASSEMBLE (or an early DATA_QUALITY_GATE) sets
the plan outcome.
"""

import uuid

from app.commerce.diagnostics.plans.handlers import HANDLERS
from app.commerce.diagnostics.plans.period import resolve_period
from app.commerce.diagnostics.plans.ports import TrustedExecutionContext
from app.commerce.diagnostics.plans.schema import (
    FAILURE_MARK_UNKNOWN,
    FAILURE_STOP,
    STEP_STATUS_FAILED,
    STEP_STATUS_MARKED_UNKNOWN,
    STEP_STATUS_SKIPPED,
    STEP_STATUS_SUCCEEDED,
    STOP_UNSUPPORTED,
)
from app.commerce.diagnostics.plans.state import PlanExecutionState
from app.commerce.diagnostics.plans.validator import MaxDepthExceededError
from app.commerce.diagnostics.plans.when import evaluate_all


class PlanContext:
    """Execution context: pinned-definition resolution + fact executor + trusted context."""

    def __init__(self, compile_context, fact_executor, trusted_context):
        self.compile_context = compile_context
        self.fact_executor = fact_executor
        self.trusted_context = trusted_context
        self.plan_ir = None

    def resolve(self, ref):
        registry = self.compile_context.registry_for(ref.kind)
        return registry.get(ref.id, ref.version)


class PlanExecutionError(Exception):
    pass


class PlanExecutor:

    def execute(self, ir, compile_context, fact_executor, subject, execution_id=None,
                trusted_context=None, analysis_period=None, comparison_period=None,
                now=None):
        state = PlanExecutionState(
            plan_id=ir.plan_id,
            plan_version=ir.version,
            checksum=ir.checksum,
            execution_id=execution_id or uuid.uuid4().hex,
            subject=subject,
        )
        state.analysis_period = (
            analysis_period if analysis_period is not None
            else resolve_period(ir.analysis_period, now)
        )
        state.comparison_period = (
            comparison_period if comparison_period is not None
            else resolve_period(ir.comparison_period, now)
        )
        context = PlanContext(compile_context, fact_executor, trusted_context)
        context.plan_ir = ir

        reachable = self._reachable(ir)
        for step in self._topological_order(ir, reachable):
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
            except MaxDepthExceededError as error:
                state.mark(step.step_id, STEP_STATUS_FAILED, str(error))
                state.errors.append(str(error))
                state.outcome = STOP_UNSUPPORTED
                break
            except Exception as error:  # noqa: BLE001 - failure policy dispatch
                state.errors.append(f"{step.step_id}: {error}")
                if step.on_failure == FAILURE_STOP:
                    state.mark(step.step_id, STEP_STATUS_FAILED, str(error))
                    state.outcome = STOP_UNSUPPORTED
                    break
                if step.on_failure == FAILURE_MARK_UNKNOWN:
                    state.mark(step.step_id, STEP_STATUS_MARKED_UNKNOWN, str(error))
                else:
                    state.mark(step.step_id, STEP_STATUS_SKIPPED, str(error))
        for step in ir.steps:
            if step.step_id not in reachable:
                state.mark(step.step_id, STEP_STATUS_SKIPPED, "unreachable")
        return state

    @staticmethod
    def _reachable(ir):
        entry = ir.entry_step_id or (ir.steps[0].step_id if ir.steps else "")
        steps = {step.step_id: step for step in ir.steps}
        reachable = set()
        if entry:
            stack = [entry]
            while stack:
                sid = stack.pop()
                if sid in reachable:
                    continue
                reachable.add(sid)
                stack.extend(steps[sid].next)
        return reachable

    @staticmethod
    def _topological_order(ir, reachable):
        steps = {step.step_id: step for step in ir.steps}
        order_index = {step.step_id: i for i, step in enumerate(ir.steps)}
        indegree = {step_id: 0 for step_id in reachable}
        for sid in reachable:
            for nxt in steps[sid].next:
                if nxt in reachable:
                    indegree[nxt] += 1
        queue = [sid for sid in indegree if indegree[sid] == 0]
        ordered = []
        while queue:
            queue.sort(key=lambda sid: order_index[sid])
            sid = queue.pop(0)
            ordered.append(steps[sid])
            for nxt in steps[sid].next:
                if nxt not in reachable:
                    continue
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)
        return ordered


__all__ = ["PlanExecutor", "PlanContext", "PlanExecutionError"]
