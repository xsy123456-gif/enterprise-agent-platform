"""Full-chain mini plan exercising all 9 typed step handlers."""

from app.commerce.diagnostics.plans import (
    FakeFactQueryExecutor,
    PlanDefinition,
    PlanExecutor,
    StepDefinition,
    STEP_ANOMALY_DETECT,
    STEP_CONTRIBUTION_ANALYZE,
    STEP_DATA_QUALITY_GATE,
    STEP_FACT_QUERY,
    STEP_IMPACT_ESTIMATE,
    STEP_METRIC_COMPUTE,
    STEP_PRIORITY_EVALUATE,
    STEP_RESULT_ASSEMBLE,
    STEP_RULE_EVALUATE,
    STOP_SUCCESS,
    TrustedExecutionContext,
)
from tests.commerce_diagnostic_plans.conftest import SUBJECT

CAP = "commerce.metrics.read"


def _fact(step_id, code, next_ids):
    return StepDefinition(step_id, STEP_FACT_QUERY,
                          {"capability": CAP, "resource": code, "evidence_code": code},
                          next=tuple(next_ids))


def _full_plan():
    return PlanDefinition(
        plan_id="full_chain_mini", version="1.0", domain="conversion",
        skill_id="store_performance_diagnosis", skill_version="1.0",
        required_capabilities=(CAP,),
        required_evidence=("REVIEW_RATING",),
        steps=(
            _fact("q_sessions", "SESSIONS", ("q_orders",)),
            _fact("q_orders", "ORDERS", ("q_review",)),
            _fact("q_review", "REVIEW_RATING", ("q_gmv",)),
            _fact("q_gmv", "GMV_BASELINE", ("cvr",)),
            StepDefinition("cvr", STEP_METRIC_COMPUTE,
                           {"metric": "CVR",
                            "inputs": {"ORDERS": "evidence:ORDERS",
                                       "SESSIONS": "evidence:SESSIONS"}},
                           next=("gate",)),
            StepDefinition("gate", STEP_DATA_QUALITY_GATE,
                           {"requirement": {"required_evidence_codes": ["REVIEW_RATING"]}},
                           next=("detect",)),
            StepDefinition("detect", STEP_ANOMALY_DETECT,
                           {"policy": "commerce.anomaly.v1", "metric": "CVR",
                            "baseline_value": 0.04, "signal_code": "CVR_DROP",
                            "domain": "conversion"}, next=("contribute",)),
            StepDefinition("contribute", STEP_CONTRIBUTION_ANALYZE,
                           {"parent_current": 900, "parent_baseline": 1000,
                            "children": [{"id": "product_A", "current": 440,
                                          "baseline": 500}]},
                           next=("rule",)),
            StepDefinition("rule", STEP_RULE_EVALUATE,
                           {"rule_set": "commerce.conversion.v1"}, next=("impact",)),
            StepDefinition("impact", STEP_IMPACT_ESTIMATE,
                           {"formula": "est_revenue_loss",
                            "inputs": {"GMV_BASELINE": "evidence:GMV_BASELINE",
                                       "DROP_RATE": 0.5}},
                           next=("priority",)),
            StepDefinition("priority", STEP_PRIORITY_EVALUATE,
                           {"policy": "commerce.priority.v1",
                            "factors": {"severity": 0.9, "business_impact": 0.8,
                                        "urgency": 0.7, "confidence": 0.8,
                                        "actionability": 0.7}},
                           next=("assemble",)),
            StepDefinition("assemble", STEP_RESULT_ASSEMBLE, {}),
        ),
    )


def _facts():
    return FakeFactQueryExecutor({
        (CAP, "SESSIONS", "store_amazon_001"): {"records": [{"value": 1000.0}]},
        (CAP, "ORDERS", "store_amazon_001"): {"records": [{"value": 20.0}]},
        (CAP, "REVIEW_RATING", "store_amazon_001"): {"records": [{"value": 3.2}]},
        (CAP, "GMV_BASELINE", "store_amazon_001"): {"records": [{"value": 100000.0}]},
    })


def test_full_chain_all_handlers(plan_registry, compile_context):
    plan_registry.register(_full_plan())
    plan_registry.activate("full_chain_mini")
    state = PlanExecutor().execute(
        plan_registry.get_active_ir("full_chain_mini"), compile_context, _facts(), SUBJECT,
        trusted_context=TrustedExecutionContext(tenant_id="company_A"),
    )
    assert state.outcome == STOP_SUCCESS
    assert state.metric_value("CVR") == 0.02
    assert state.contributions.explained_change == -60.0
    assert state.contributions.coverage == 0.6
    assert state.causes[0].cause_code == "PRODUCT_REPUTATION_DETERIORATION"
    assert state.impacts[0].value == 50000.0
    assert state.priority.level in ("P0", "P1")
    assert state.diagnostic_result is not None
