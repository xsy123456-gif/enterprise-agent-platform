"""SkillSystem — composition of Skills over the DiagnosticPlan framework.

``build_skill_system`` wires the 15 DiagnosticPlans (compiled + activated) and
the 7 Business Skills, then exposes a deterministic ``run`` entrypoint that
executes a Skill without any LLM.
"""

from dataclasses import dataclass, field

from app.commerce.diagnostics import (
    DiagnosticPolicyRegistry,
    ImpactFormulaRegistry,
    PriorityPolicyRegistry,
    RuleSetRegistry,
    build_core_metric_registry,
)
from app.commerce.diagnostics.definitions.business import (
    build_business_diagnostic_policies,
    build_business_impact_formulas,
    build_business_priority_policy,
    build_business_rule_sets,
)
from app.commerce.diagnostics.plans import (
    CompileContext,
    DiagnosticPlanRegistry,
)
from app.commerce.diagnostics.plans.definitions.business import (
    build_business_plan_definitions,
)
from app.commerce.skills.definitions import build_business_skill_definitions
from app.commerce.skills.registry import SkillRegistry
from app.commerce.skills.skill import Skill


def _build_compile_context():
    policy_registry = DiagnosticPolicyRegistry()
    for policy in build_business_diagnostic_policies():
        policy_registry.register(policy)
    ruleset_registry = RuleSetRegistry()
    for rule_set in build_business_rule_sets():
        ruleset_registry.register(rule_set)
    impact_registry = ImpactFormulaRegistry()
    for formula in build_business_impact_formulas():
        impact_registry.register(formula)
    priority_registry = PriorityPolicyRegistry()
    priority_registry.register(build_business_priority_policy())
    return CompileContext(
        metric_registry=build_core_metric_registry(),
        policy_registry=policy_registry,
        ruleset_registry=ruleset_registry,
        impact_registry=impact_registry,
        priority_registry=priority_registry,
    )


@dataclass
class SkillSystem:
    compile_context: CompileContext
    plan_registry: DiagnosticPlanRegistry
    skill_registry: SkillRegistry
    skills: dict = field(default_factory=dict)

    def run(self, skill_id, subject, trusted_context=None, fact_executor=None,
            plan_id=None, execution_id=None, skill_version=None):
        from app.commerce.skills.models import SkillInput
        definition = (
            self.skill_registry.get(skill_id, skill_version)
            if skill_version is not None
            else self.skill_registry.get_active_skill(skill_id)
        )
        skill = Skill(definition, self.plan_registry, self.compile_context)
        return skill.execute(
            SkillInput(subject=subject, plan_id=plan_id),
            trusted_context=trusted_context,
            fact_executor=fact_executor,
            execution_id=execution_id,
        )

    def skill_definition(self, skill_id, version=None):
        return self.skill_registry.get(skill_id, version)


def build_skill_system():
    """Build a fully wired SkillSystem with the 15 plans + 7 skills.

    Skills are registered (DRAFT), validated (capability + plan consistency),
    then activated (all bound plans must be ACTIVE).
    """
    compile_context = _build_compile_context()
    plan_registry = DiagnosticPlanRegistry(compile_context)
    for plan in build_business_plan_definitions():
        plan_registry.register(plan)
        plan_registry.activate(plan.plan_id)
    skill_registry = SkillRegistry(plan_registry=plan_registry)
    skills = {}
    for definition in build_business_skill_definitions():
        skill_registry.register(definition)
        skill_registry.validate(definition.skill_id)
        skill_registry.activate(definition.skill_id)
        skills[definition.skill_id] = Skill(definition, plan_registry,
                                            compile_context)
    return SkillSystem(
        compile_context=compile_context,
        plan_registry=plan_registry,
        skill_registry=skill_registry,
        skills=skills,
    )


__all__ = ["SkillSystem", "build_skill_system"]
