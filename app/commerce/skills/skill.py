"""Skill executor.

A Skill resolves a versioned DiagnosticPlan and runs it deterministically
(validate input -> resolve plan -> bind context -> execute -> return
DiagnosticResult).  No LLM, no prompt.
"""

from app.commerce.diagnostics.plans import PlanExecutor
from app.commerce.skills.errors import UnknownPlanForSkill


class Skill:
    """Deterministic execution wrapper over a DiagnosticPlan."""

    def __init__(self, definition, plan_registry, compile_context):
        self.definition = definition
        self.plan_registry = plan_registry
        self.compile_context = compile_context

    def execute(self, input, trusted_context=None, fact_executor=None,
                execution_id=None):
        """Validate input, resolve the plan, execute, and return the
        ``DiagnosticResult``.

        ``fact_executor`` is a ``FactQueryExecutorPort`` injected by the caller
        (production ToolRunner adapter or a test fake).  ``trusted_context`` is
        the Runtime-injected ``TrustedExecutionContext``.
        """
        if input is None or input.subject is None:
            from app.commerce.skills.errors import SkillError
            raise SkillError("skill input requires a subject")
        if fact_executor is None:
            from app.commerce.skills.errors import SkillError
            raise SkillError("skill requires a FactQueryExecutorPort")
        plan_id = input.plan_id or self.definition.default_plan_id
        if not self.definition.supports(plan_id):
            raise UnknownPlanForSkill(
                f"plan {plan_id!r} is not supported by skill "
                f"{self.definition.skill_id!r}"
            )
        ir = self.plan_registry.get_active_ir(plan_id)
        state = PlanExecutor().execute(
            ir, self.compile_context, fact_executor, input.subject,
            trusted_context=trusted_context, execution_id=execution_id,
        )
        return state.diagnostic_result


__all__ = ["Skill"]
