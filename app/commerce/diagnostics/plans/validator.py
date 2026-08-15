"""Plan Validator — structural + DAG + WHEN safety checks (fail-closed)."""

from app.commerce.diagnostics.errors import MetricError
from app.commerce.diagnostics.plans.schema import (
    FAILURE_POLICIES,
    STEP_FACT_QUERY,
    STEP_RESULT_ASSEMBLE,
    STEP_TYPES,
)
from app.commerce.diagnostics.plans.when import (
    WHEN_OPERATORS,
    is_allowed_path,
)


class PlanValidationError(MetricError):
    """A DiagnosticPlan definition is invalid."""


class MaxDepthExceededError(PlanValidationError):
    """A plan's drill-down depth exceeds its declared ``max_depth``."""


class SecurityFieldViolation(PlanValidationError):
    """A reserved security field appeared in untrusted plan/query params."""


# Reserved security field names (normalized).  These must never appear in
# untrusted plan/step/query params — even though they cannot override the
# TrustedExecutionContext, their presence is rejected fail-closed.
RESERVED_SECURITY_FIELDS = frozenset({
    "tenant", "tenantid", "principal", "principalid", "organization",
    "organizationid", "org", "orgid", "role", "roles", "scope", "scopes",
    "permission", "permissions", "clearance", "securityclearance",
    "accesscontext", "user", "userid", "actor",
})


def _normalize_key(key):
    return str(key).lower().replace("_", "").replace("-", "")


def _scan_security_fields(value, path, violations):
    if isinstance(value, dict):
        for key, item in value.items():
            if _normalize_key(key) in RESERVED_SECURITY_FIELDS:
                violations.append(f"{path}.{key}")
            _scan_security_fields(item, f"{path}.{key}", violations)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _scan_security_fields(item, f"{path}[{index}]", violations)


def validate_plan(definition):
    if not definition.plan_id:
        raise PlanValidationError("plan_id is required")
    if not definition.version:
        raise PlanValidationError(f"plan {definition.plan_id!r} requires a version")
    if not definition.domain:
        raise PlanValidationError(f"plan {definition.plan_id!r} requires a domain")
    if not definition.steps:
        raise PlanValidationError(f"plan {definition.plan_id!r} has no steps")

    all_ids = {step.step_id for step in definition.steps}
    if len(all_ids) != len(definition.steps):
        raise PlanValidationError(f"plan {definition.plan_id!r} has duplicate step ids")

    for step in definition.steps:
        if step.type not in STEP_TYPES:
            raise PlanValidationError(
                f"step {step.step_id!r} has unknown type {step.type!r}"
            )
        if step.on_failure not in FAILURE_POLICIES:
            raise PlanValidationError(
                f"step {step.step_id!r} has unknown on_failure {step.on_failure!r}"
            )
        for condition in step.when:
            if not is_allowed_path(condition.path):
                raise PlanValidationError(
                    f"step {step.step_id!r} has unsupported WHEN path "
                    f"{condition.path!r}"
                )
            if condition.operator not in WHEN_OPERATORS:
                raise PlanValidationError(
                    f"step {step.step_id!r} has unsupported WHEN operator "
                    f"{condition.operator!r}"
                )
        for target in step.next:
            if target not in all_ids:
                raise PlanValidationError(
                    f"step {step.step_id!r} references unknown next step {target!r}"
                )

    _check_capabilities(definition)
    _check_security_fields(definition)
    _check_acyclic(definition)
    _check_result_assemble(definition)
    _check_drill_depth(definition)


def _check_security_fields(definition):
    violations = []
    for step in definition.steps:
        _scan_security_fields(step.params, f"step.{step.step_id}.params", violations)
    _scan_security_fields(definition.analysis_period, "analysis_period", violations)
    _scan_security_fields(definition.comparison_period, "comparison_period", violations)
    if violations:
        raise SecurityFieldViolation(
            f"reserved security fields found: {', '.join(sorted(violations))}"
        )


def _check_capabilities(definition):
    declared = set(definition.required_capabilities)
    for step in definition.steps:
        if step.type != STEP_FACT_QUERY:
            continue
        capability = step.params.get("capability")
        if not capability:
            raise PlanValidationError(
                f"FACT_QUERY step {step.step_id!r} must declare a capability"
            )
        if capability not in declared:
            raise PlanValidationError(
                f"FACT_QUERY step {step.step_id!r} references undeclared "
                f"capability {capability!r}"
            )


def _check_drill_depth(definition):
    for step in definition.steps:
        if step.type != STEP_FACT_QUERY:
            continue
        depth = step.params.get("drill_depth", 1)
        if depth > definition.max_depth:
            raise MaxDepthExceededError(
                f"FACT_QUERY step {step.step_id!r} drill_depth {depth} exceeds "
                f"plan max_depth {definition.max_depth}"
            )


def _check_acyclic(definition):
    steps = {s.step_id: s for s in definition.steps}
    state = {}

    def visit(step_id, stack):
        if state.get(step_id) == 2:
            return
        if state.get(step_id) == 1:
            raise PlanValidationError(
                f"plan {definition.plan_id!r} has a cycle at {step_id!r}"
            )
        state[step_id] = 1
        for target in steps[step_id].next:
            visit(target, stack | {step_id})
        state[step_id] = 2

    for step_id in steps:
        visit(step_id, frozenset())


def _check_result_assemble(definition):
    assembles = [s for s in definition.steps if s.type == STEP_RESULT_ASSEMBLE]
    if len(assembles) != 1:
        raise PlanValidationError(
            f"plan {definition.plan_id!r} must have exactly one RESULT_ASSEMBLE step"
        )
    if assembles[0].next:
        raise PlanValidationError("RESULT_ASSEMBLE must be a terminal step")


__all__ = [
    "validate_plan",
    "PlanValidationError",
    "MaxDepthExceededError",
    "SecurityFieldViolation",
    "RESERVED_SECURITY_FIELDS",
]
