"""Phase 18.15.6 remediation tests: signal wiring + failure-policy hardening."""

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
    ScenarioInput,
    run_scenario,
)

CAP_METRICS = "commerce.metrics.read"
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


def test_traffic_decline_signal_and_cause_wired(plans, compile_context):
    # GMV + SESSIONS decline, CVR stable -> TRAFFIC_DROP -> TRAFFIC_DECLINE.
    facts = make_facts(
        (CAP_METRICS, "GMV", 1000.0), (CAP_METRICS, "GMV_B", 2000.0),
        (CAP_METRICS, "ORDERS", 20.0), (CAP_METRICS, "ORDERS_B", 40.0),
        (CAP_METRICS, "SESSIONS", 1000.0), (CAP_METRICS, "SESSIONS_B", 2000.0),
    )
    state = _run(plans, compile_context, "store_health_scan", facts)
    signals = {s.signal_code for s in state.signals}
    assert "TRAFFIC_DROP" in signals
    primary = {c.cause_code for c in state.causes if c.causal_role == "PRIMARY"}
    assert "TRAFFIC_DECLINE" in primary


def test_stable_sessions_does_not_emit_false_traffic_drop(plans, compile_context):
    # CVR-only decline (sessions flat) must NOT emit TRAFFIC_DROP.
    facts = make_facts(
        (CAP_METRICS, "GMV", 1000.0), (CAP_METRICS, "GMV_B", 2000.0),
        (CAP_METRICS, "ORDERS", 20.0), (CAP_METRICS, "ORDERS_B", 40.0),
        (CAP_METRICS, "SESSIONS", 2000.0), (CAP_METRICS, "SESSIONS_B", 2000.0),
    )
    state = _run(plans, compile_context, "store_health_scan", facts)
    traffic = [s for s in state.signals if s.signal_code == "TRAFFIC_DROP"]
    assert all(s.status not in ("ABNORMAL", "CRITICAL") for s in traffic)


def test_ad_efficiency_signal_and_cause_wired(plans, compile_context):
    # ROAS down + CPC up -> TRAFFIC_COST_INCREASE.
    facts = make_facts(
        (CAP_METRICS, "AD_SALES", 5000.0), (CAP_METRICS, "AD_SALES_B", 10000.0),
        (CAP_METRICS, "AD_SPEND", 5000.0), (CAP_METRICS, "AD_SPEND_B", 5000.0),
        (CAP_METRICS, "CLICKS", 200.0), (CAP_METRICS, "CLICKS_B", 300.0),
        (CAP_METRICS, "IMPRESSIONS", 10000.0), (CAP_METRICS, "IMPRESSIONS_B", 10000.0),
    )
    state = _run(plans, compile_context, "advertising_health_scan", facts)
    signals = {s.signal_code for s in state.signals}
    assert "ROAS_DROP" in signals
    assert "CPC_RISE" in signals
    primary = {c.cause_code for c in state.causes if c.causal_role == "PRIMARY"}
    assert "TRAFFIC_COST_INCREASE" in primary


def test_missing_evidence_does_not_yield_none_diagnostic(plans, compile_context):
    # All required facts absent -> typed INSUFFICIENT_DATA, never None.
    state = _run(plans, compile_context, "store_health_scan", {})
    assert state.diagnostic_result is not None
    assert state.diagnostic_result.status == "INSUFFICIENT_DATA"
    assert state.diagnostic_result.causes == ()
