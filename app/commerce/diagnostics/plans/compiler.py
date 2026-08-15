"""Plan Compiler — pins all definition references to explicit versions.

Given a validated ``PlanDefinition`` and the definition registries, the compiler
resolves every referenced metric / policy / rule set / impact formula / priority
policy to a concrete ``(id, version)`` and produces an immutable ``PlanIR``.
After compilation the plan never drifts with the active version.
"""

from dataclasses import dataclass

from app.commerce.diagnostics.plans.ir import (
    REF_IMPACT_FORMULA,
    REF_METRIC,
    REF_POLICY,
    REF_PRIORITY_POLICY,
    REF_RULE_SET,
    CompiledStep,
    PinnedRef,
    PlanIR,
)
from app.commerce.diagnostics.plans.schema import (
    STEP_ANOMALY_DETECT,
    STEP_IMPACT_ESTIMATE,
    STEP_METRIC_COMPUTE,
    STEP_PRIORITY_EVALUATE,
    STEP_RULE_EVALUATE,
    PlanDefinition,
)
from app.commerce.diagnostics.plans.validator import validate_plan

# step type -> {param_key: ref_kind}
_REFERENCE_PARAMS = {
    STEP_METRIC_COMPUTE: {"metric": REF_METRIC},
    STEP_ANOMALY_DETECT: {"policy": REF_POLICY},
    STEP_RULE_EVALUATE: {"rule_set": REF_RULE_SET},
    STEP_IMPACT_ESTIMATE: {"formula": REF_IMPACT_FORMULA},
    STEP_PRIORITY_EVALUATE: {"policy": REF_PRIORITY_POLICY},
}


@dataclass
class CompileContext:
    metric_registry: object = None
    policy_registry: object = None
    ruleset_registry: object = None
    impact_registry: object = None
    priority_registry: object = None

    def registry_for(self, kind):
        return {
            REF_METRIC: self.metric_registry,
            REF_POLICY: self.policy_registry,
            REF_RULE_SET: self.ruleset_registry,
            REF_IMPACT_FORMULA: self.impact_registry,
            REF_PRIORITY_POLICY: self.priority_registry,
        }[kind]


def _resolve_ref(kind, registry, value):
    if "@" in value:
        name, _, version = value.partition("@")
    else:
        name, version = value, None
    definition = registry.get(name, version)
    return PinnedRef(kind=kind, id=name, version=definition.version)


class PlanCompiler:

    def compile(self, definition: PlanDefinition, context: CompileContext) -> PlanIR:
        validate_plan(definition)
        dependencies = {}
        compiled_steps = []
        for step in definition.steps:
            params = dict(step.params)
            ref_params = _REFERENCE_PARAMS.get(step.type, {})
            for param_key, ref_kind in ref_params.items():
                if param_key not in params:
                    continue
                ref = _resolve_ref(ref_kind, context.registry_for(ref_kind),
                                   params.pop(param_key))
                params[f"{param_key}_ref"] = ref
                dependencies[(ref.kind, ref.id, ref.version)] = ref
            compiled_steps.append(CompiledStep(
                step_id=step.step_id, type=step.type, params=params,
                when=step.when, on_failure=step.on_failure, next=step.next,
            ))
        ir = PlanIR(
            plan_id=definition.plan_id,
            version=definition.version,
            domain=definition.domain,
            skill_id=definition.skill_id,
            skill_version=definition.skill_version,
            steps=tuple(compiled_steps),
            dependencies=tuple(sorted(dependencies.values(),
                                      key=lambda r: (r.kind, r.id, r.version))),
            required_evidence=definition.required_evidence,
            optional_evidence=definition.optional_evidence,
            max_depth=definition.max_depth,
            analysis_period=definition.analysis_period,
            comparison_period=definition.comparison_period,
        )
        checksum = ir.compute_checksum()
        from dataclasses import replace
        return replace(ir, checksum=checksum)


__all__ = ["PlanCompiler", "CompileContext"]
