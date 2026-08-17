"""Phase 9 business DiagnosticPlans tests: validity, versioning, compilation,
and threshold/formula/tool-id absence."""

import pytest

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
    PlanCompiler,
    validate_plan,
)
from app.commerce.diagnostics.plans.definitions.business import (
    build_business_plan_definitions,
)

EXPECTED_PLAN_IDS = {
    "store_health_scan", "gmv_decline_diagnosis", "conversion_decline_diagnosis",
    "product_anomaly_diagnosis", "slow_moving_inventory",
    "advertising_health_scan", "roas_decline_diagnosis", "high_spend_low_conversion",
    "search_term_waste", "stockout_risk", "inventory_sales_imbalance",
    "rating_deterioration", "emerging_product_issue", "product_360",
    "daily_operations_scan",
}

_TOOL_IDS = {
    "store.get", "catalog.query", "metric.query", "inventory.query",
    "review.query", "advertising.query",
}


@pytest.fixture(scope="module")
def plans():
    return list(build_business_plan_definitions())


@pytest.fixture(scope="module")
def compile_context():
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


def _walk(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk(item)
    else:
        yield value


def test_fifteen_plans_present(plans):
    ids = {plan.plan_id for plan in plans}
    assert ids == EXPECTED_PLAN_IDS
    assert len(plans) == 15


def test_all_plans_pass_validator(plans):
    from app.commerce.diagnostics.plans import validate_plan
    for plan in plans:
        validate_plan(plan)


def test_all_plans_compile_and_pin_versions(plans, compile_context):
    compiler = PlanCompiler()
    for plan in plans:
        ir = compiler.compile(plan, compile_context)
        assert ir.checksum
        assert ir.dependencies  # every plan pins at least a policy + rule set


def test_plans_are_versioned(plans):
    for plan in plans:
        assert plan.version == "1.0"
        assert plan.plan_id


def test_no_numeric_thresholds_in_step_params(plans):
    for plan in plans:
        for step in plan.steps:
            for value in _walk(step.params):
                assert not isinstance(value, (int, float)), (
                    f"{plan.plan_id}:{step.step_id} contains a numeric literal "
                    f"{value!r} (thresholds must live in definitions)"
                )


def test_no_formulas_in_step_params(plans):
    for plan in plans:
        for step in plan.steps:
            for value in _walk(step.params):
                if isinstance(value, str):
                    assert "/" not in value, (
                        f"{plan.plan_id}:{step.step_id} inlines a formula {value!r}"
                    )


def test_no_tool_implementation_ids(plans):
    for plan in plans:
        for step in plan.steps:
            for value in _walk(step.params):
                assert value not in _TOOL_IDS, (
                    f"{plan.plan_id}:{step.step_id} references tool "
                    f"implementation {value!r} (use a capability)"
                )


def test_fact_queries_declare_capabilities(plans):
    from app.commerce.diagnostics.plans.schema import STEP_FACT_QUERY
    for plan in plans:
        for step in plan.steps:
            if step.type == STEP_FACT_QUERY:
                assert step.params.get("capability") in plan.required_capabilities


def test_metric_refs_resolve(plans, compile_context):
    # Every METRIC_COMPUTE metric name must exist in the metric registry.
    from app.commerce.diagnostics.plans.schema import STEP_METRIC_COMPUTE
    for plan in plans:
        for step in plan.steps:
            if step.type == STEP_METRIC_COMPUTE:
                compile_context.metric_registry.get(step.params["metric"])
