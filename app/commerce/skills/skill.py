"""Skill executor.

A Skill resolves a versioned DiagnosticPlan and runs it deterministically
(validate input -> resolve plan -> bind context -> execute -> return a
``SkillResult`` wrapping the DiagnosticResult).  No LLM, no prompt.
"""

from datetime import datetime, timezone

from app.commerce.diagnostics.plans import PlanExecutor
from app.commerce.skills.errors import UnknownPlanForSkill
from app.commerce.skills.models import SkillResult


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class Skill:
    """Deterministic execution wrapper over a DiagnosticPlan."""

    def __init__(self, definition, plan_registry, compile_context):
        self.definition = definition
        self.plan_registry = plan_registry
        self.compile_context = compile_context

    def execute(self, input, trusted_context=None, fact_executor=None,
                execution_id=None):
        """Validate input, resolve the plan, execute, and return a ``SkillResult``.

        ``fact_executor`` is a ``FactQueryExecutorPort`` injected by the caller
        (production ToolRunner adapter or a test fake).  ``trusted_context`` is
        the Runtime-injected ``TrustedExecutionContext``.
        """
        from app.commerce.skills.errors import SkillError
        if input is None or input.subject is None:
            raise SkillError("skill input requires a subject")
        if fact_executor is None:
            raise SkillError("skill requires a FactQueryExecutorPort")
        plan_id = input.plan_id or self.definition.default_plan_id
        if not self.definition.supports(plan_id):
            raise UnknownPlanForSkill(
                f"plan {plan_id!r} is not supported by skill "
                f"{self.definition.skill_id!r}"
            )
        ir = self.plan_registry.get_active_ir(plan_id)
        started_at = utc_now()
        state = PlanExecutor().execute(
            ir, self.compile_context, fact_executor, input.subject,
            trusted_context=trusted_context, execution_id=execution_id,
        )
        return SkillResult(
            skill_id=self.definition.skill_id,
            skill_version=self.definition.version,
            plan_id=plan_id,
            plan_version=ir.version,
            diagnostic_result=state.diagnostic_result,
            execution_id=state.execution_id,
            trace_id=input.trace_id,
            started_at=started_at,
            completed_at=utc_now(),
        )


__all__ = ["Skill"]
