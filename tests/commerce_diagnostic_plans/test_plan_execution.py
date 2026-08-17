"""Phase 9 execution-level validation: full PlanExecutor -> Metric -> Signal ->
Cause -> Impact -> Priority -> DiagnosticResult chains for the key plans."""

import pytest

from app.commerce.contracts.subject import SubjectRef
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
from app.commerce.diagnostics.plans import CompileContext
from app.commerce.diagnostics.plans.definitions.business import (
    build_business_plan_definitions,
)
from app.commerce.diagnostics.plans.scenario import (
    GroundTruth,
    ScenarioInput,
    assert_ground_truth,
    run_scenario,
)

CAP_METRICS = "commerce.metrics.read"
CAP_REVIEW = "commerce.review.read"
CAP_INVENTORY = "commerce.inventory.read"
CAP_ADVERTISING = "commerce.advertising.read"

SUBJECT = SubjectRef("STORE", "JP01")


@pytest.fixture(scope="module")
def plans():
    return {plan.plan_id: plan for plan in build_business_plan_definitions()}


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


def make_facts(*items):
    facts = {}
    for capability, resource, value in items:
        facts[(capability, resource, SUBJECT.id)] = {"records": [{"value": value}]}
    return facts


def _run(plans, compile_context, plan_id, facts):
    return run_scenario(
        plans[plan_id], compile_context,
        ScenarioInput(scenario_id=f"scn-{plan_id}", plan_id=plan_id,
                      subject=SUBJECT, facts=facts),
    )


# ── 1. store_health_scan ────────────────────────────────────

def test_store_health_scan_execution(plans, compile_context):
    facts = make_facts(
        (CAP_METRICS, "GMV", 1000.0), (CAP_METRICS, "GMV_B", 2000.0),
        (CAP_METRICS, "ORDERS", 20.0), (CAP_METRICS, "ORDERS_B", 40.0),
        (CAP_METRICS, "SESSIONS", 1000.0), (CAP_METRICS, "SESSIONS_B", 1000.0),
    )
    state = _run(plans, compile_context, "store_health_scan", facts)
    assert_ground_truth(state, GroundTruth(expected_signals=("GMV_DROP", "CVR_DROP")))
    assert state.diagnostic_result.status == "COMPLETED"


# ── 2. gmv_decline_diagnosis ────────────────────────────────

def test_gmv_decline_execution(plans, compile_context):
    facts = make_facts(
        (CAP_METRICS, "GMV", 1000.0), (CAP_METRICS, "GMV_B", 2000.0),
        (CAP_METRICS, "ORDERS", 20.0), (CAP_METRICS, "ORDERS_B", 20.0),
        (CAP_METRICS, "SESSIONS", 1000.0), (CAP_METRICS, "SESSIONS_B", 1000.0),
        (CAP_METRICS, "DROP_RATE", 0.5),
    )
    state = _run(plans, compile_context, "gmv_decline_diagnosis", facts)
    assert_ground_truth(state, GroundTruth(
        expected_signals=("GMV_DROP", "AOV_DROP"),
        primary_causes=("PRODUCT_MIX_SHIFT",),
        expected_priority="P2",
    ))
    # Impact was produced with governance fields.
    assert state.impacts
    assert state.impacts[0].classification == "ESTIMATED"
    assert state.impacts[0].formula_id == "est_revenue_loss"
    assert state.impacts[0].formula_version == "1.0"


# ── 3. conversion_decline (false correlation) ───────────────

def test_conversion_decline_false_correlation(plans, compile_context):
    facts = make_facts(
        (CAP_METRICS, "ORDERS", 20.0), (CAP_METRICS, "ORDERS_B", 40.0),
        (CAP_METRICS, "SESSIONS", 1000.0), (CAP_METRICS, "SESSIONS_B", 1000.0),
        (CAP_METRICS, "GMV", 1000.0), (CAP_METRICS, "GMV_B", 2000.0),
        (CAP_METRICS, "REVIEW_RATING", 3.9),
        (CAP_REVIEW, "PRICE_INDEX", 1.15),
        (CAP_METRICS, "NEGATIVE_REVIEW_RATE", 0.06),
        (CAP_METRICS, "NEGATIVE_REVIEW_RATE_B", 0.05),
        (CAP_METRICS, "DROP_RATE", 0.5),
    )
    state = _run(plans, compile_context, "conversion_decline_diagnosis", facts)
    assert_ground_truth(state, GroundTruth(
        expected_signals=("CVR_DROP",),
        primary_causes=("PRICE_INCREASE",),
        excluded_causes=("PRODUCT_REPUTATION_DETERIORATION",),
        expected_priority="P2",
    ))
    # The reputation cause (if present) must NOT be PRIMARY.
    reputation = next(
        (c for c in state.causes if c.cause_code == "PRODUCT_REPUTATION_DETERIORATION"),
        None,
    )
    if reputation is not None:
        assert reputation.causal_role != "PRIMARY"


# ── 4. conversion_decline (missing evidence) ────────────────

def test_conversion_decline_missing_review_evidence(plans, compile_context):
    facts = make_facts(
        (CAP_METRICS, "ORDERS", 20.0), (CAP_METRICS, "ORDERS_B", 40.0),
        (CAP_METRICS, "SESSIONS", 1000.0), (CAP_METRICS, "SESSIONS_B", 1000.0),
        (CAP_METRICS, "GMV", 1000.0), (CAP_METRICS, "GMV_B", 2000.0),
        # REVIEW_RATING is NOT provided -> required evidence missing.
        (CAP_REVIEW, "PRICE_INDEX", 1.0),
        (CAP_METRICS, "NEGATIVE_REVIEW_RATE", 0.06),
        (CAP_METRICS, "NEGATIVE_REVIEW_RATE_B", 0.05),
        (CAP_METRICS, "DROP_RATE", 0.5),
    )
    state = _run(plans, compile_context, "conversion_decline_diagnosis", facts)
    reputation = next(
        (c for c in state.causes if c.cause_code == "PRODUCT_REPUTATION_DETERIORATION"),
        None,
    )
    # The reputation cause is a candidate but INSUFFICIENT_EVIDENCE, not CONFIRMED.
    assert reputation is not None
    assert reputation.support_level == "INSUFFICIENT_EVIDENCE"
    assert reputation.support_level != "CONFIRMED"


# ── 5. high_spend_low_conversion ────────────────────────────

def test_high_spend_low_conversion_execution(plans, compile_context):
    facts = make_facts(
        (CAP_METRICS, "AD_SPEND", 1000.0), (CAP_METRICS, "AD_SPEND_B", 500.0),
        (CAP_METRICS, "AD_CLICKS", 100.0), (CAP_METRICS, "AD_CLICKS_B", 100.0),
        (CAP_METRICS, "AD_ORDERS", 2.0), (CAP_METRICS, "AD_ORDERS_B", 10.0),
        (CAP_METRICS, "DROP_RATE", 0.5),
    )
    state = _run(plans, compile_context, "high_spend_low_conversion", facts)
    assert_ground_truth(state, GroundTruth(
        expected_signals=("SPEND_RISE", "AD_CVR_DROP"),
        expected_priority="P2",
    ))


# ── 6. search_term_waste ────────────────────────────────────

def test_search_term_waste_execution(plans, compile_context):
    facts = make_facts(
        (CAP_ADVERTISING, "SEARCH_TERM_SPEND", 800.0),
        (CAP_ADVERTISING, "SEARCH_TERM_SPEND_B", 100.0),
        (CAP_METRICS, "DROP_RATE", 0.5),
    )
    state = _run(plans, compile_context, "search_term_waste", facts)
    assert_ground_truth(state, GroundTruth(
        expected_signals=("SEARCH_TERM_WASTE",),
        primary_causes=("IRRELEVANT_SEARCH_TERM_SPEND",),
        expected_priority="P2",
    ))
    assert state.impacts
    assert state.impacts[0].classification == "OBSERVED"


# ── 7. stockout_risk ────────────────────────────────────────

def test_stockout_risk_execution(plans, compile_context):
    facts = make_facts(
        (CAP_METRICS, "AVAILABLE_INVENTORY", 30.0),
        (CAP_METRICS, "AVAILABLE_INVENTORY_B", 300.0),
        (CAP_METRICS, "UNITS", 100.0), (CAP_METRICS, "UNITS_B", 100.0),
        (CAP_METRICS, "PERIOD_DAYS", 10.0), (CAP_METRICS, "PERIOD_DAYS_B", 10.0),
        (CAP_METRICS, "DAILY_REVENUE", 1000.0),
        (CAP_METRICS, "STOCKOUT_DAYS", 3.0),
        (CAP_METRICS, "DROP_RATE", 0.8),
    )
    state = _run(plans, compile_context, "stockout_risk", facts)
    assert_ground_truth(state, GroundTruth(
        expected_signals=("DAYS_OF_SUPPLY_LOW",),
        primary_causes=("STOCKOUT_RISK",),
    ))
    assert state.impacts
    assert state.impacts[0].classification == "PROJECTED"


# ── 8. rating_deterioration ─────────────────────────────────

def test_rating_deterioration_execution(plans, compile_context):
    facts = make_facts(
        (CAP_METRICS, "REVIEW_RATING", 3.2), (CAP_METRICS, "REVIEW_RATING_B", 4.5),
        (CAP_METRICS, "NEGATIVE_REVIEW_RATE", 0.20),
        (CAP_METRICS, "NEGATIVE_REVIEW_RATE_B", 0.05),
        (CAP_METRICS, "DROP_RATE", 0.3),
    )
    state = _run(plans, compile_context, "rating_deterioration", facts)
    assert_ground_truth(state, GroundTruth(
        expected_signals=("RATING_DROP", "NEGATIVE_REVIEW_RATE_RISE"),
        primary_causes=("PRODUCT_REPUTATION_DETERIORATION",),
    ))


# ── 9. product_360 ──────────────────────────────────────────

def test_product_360_execution(plans, compile_context):
    facts = make_facts(
        (CAP_METRICS, "UNITS", 50.0), (CAP_METRICS, "UNITS_B", 100.0),
        (CAP_METRICS, "ORDERS", 20.0), (CAP_METRICS, "ORDERS_B", 40.0),
        (CAP_METRICS, "SESSIONS", 1000.0), (CAP_METRICS, "SESSIONS_B", 1000.0),
        (CAP_METRICS, "GMV", 1000.0), (CAP_METRICS, "GMV_B", 2000.0),
        (CAP_METRICS, "AD_SPEND", 100.0), (CAP_METRICS, "AD_SPEND_B", 100.0),
        (CAP_METRICS, "AD_SALES", 200.0), (CAP_METRICS, "AD_SALES_B", 400.0),
        (CAP_METRICS, "REVIEW_RATING", 3.2), (CAP_METRICS, "REVIEW_RATING_B", 4.5),
        (CAP_METRICS, "DROP_RATE", 0.5),
    )
    state = _run(plans, compile_context, "product_360", facts)
    signals = {s.signal_code for s in state.signals}
    assert {"UNITS_DROP", "CVR_DROP", "ROAS_DROP", "RATING_DROP"} <= signals
    assert state.diagnostic_result is not None


# ── 10. daily_operations_scan structure ─────────────────────

def test_daily_operations_scan_is_aggregation_only(plans):
    from app.commerce.diagnostics.plans.schema import (
        STEP_IMPACT_ESTIMATE,
        STEP_PRIORITY_EVALUATE,
        STEP_RULE_EVALUATE,
    )
    daily = plans["daily_operations_scan"]
    types = {step.type for step in daily.steps}
    # The triage plan does NOT re-implement the deep diagnosis.
    assert STEP_RULE_EVALUATE not in types
    assert STEP_IMPACT_ESTIMATE not in types
    assert STEP_PRIORITY_EVALUATE not in types
    # Domain plans own the deep diagnosis.
    assert STEP_RULE_EVALUATE in {s.type for s in plans["store_health_scan"].steps}


# ── 11. Impact / Priority runtime governance fields ─────────

def test_impact_and_priority_runtime_fields(plans, compile_context):
    facts = make_facts(
        (CAP_METRICS, "GMV", 1000.0), (CAP_METRICS, "GMV_B", 2000.0),
        (CAP_METRICS, "ORDERS", 20.0), (CAP_METRICS, "ORDERS_B", 20.0),
        (CAP_METRICS, "SESSIONS", 1000.0), (CAP_METRICS, "SESSIONS_B", 1000.0),
        (CAP_METRICS, "DROP_RATE", 0.5),
    )
    state = _run(plans, compile_context, "gmv_decline_diagnosis", facts)
    impact = state.impacts[0]
    assert impact.formula_id == "est_revenue_loss"
    assert impact.formula_version == "1.0"
    assert impact.classification == "ESTIMATED"
    assert impact.impact_type == "REVENUE_LOSS"
    priority = state.priority
    assert priority.policy_id == "commerce.priority.v1"
    assert priority.policy_version == "1.0"
    assert priority.level in ("P0", "P1", "P2", "P3")
    assert priority.score is not None
