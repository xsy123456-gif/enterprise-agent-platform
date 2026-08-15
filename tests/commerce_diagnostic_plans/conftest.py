"""Shared fixtures for DiagnosticPlan Framework tests."""

import pytest

from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics import (
    DiagnosticPolicy,
    DiagnosticPolicyRegistry,
    ImpactFormula,
    ImpactFormulaRegistry,
    PriorityPolicy,
    PriorityPolicyRegistry,
    Rule,
    RuleCondition,
    RuleConsequent,
    RuleSet,
    RuleSetRegistry,
    build_core_metric_registry,
)
from app.commerce.diagnostics.plans import (
    CompileContext,
    DiagnosticPlanRegistry,
    FakeFactQueryExecutor,
    PlanDefinition,
    StepDefinition,
    STEP_ANOMALY_DETECT,
    STEP_FACT_QUERY,
    STEP_METRIC_COMPUTE,
    STEP_RESULT_ASSEMBLE,
    STEP_RULE_EVALUATE,
)

SUBJECT = SubjectRef("STORE", "store_amazon_001")


@pytest.fixture
def compile_context():
    metric_registry = build_core_metric_registry()
    policy_registry = DiagnosticPolicyRegistry()
    policy_registry.register(DiagnosticPolicy(
        policy_id="commerce.anomaly.v1", version="1.0",
        min_baseline_volume=0.0001, min_sample_size=0,
    ))
    ruleset_registry = RuleSetRegistry()
    ruleset_registry.register(RuleSet(
        rule_set_id="commerce.conversion.v1", version="1.0", domain="conversion",
        rules=[
            Rule(rule_id="cvr_drop_review", version="1.0",
                 antecedents=[RuleCondition("CVR_DROP", "ABNORMAL", "DOWN")],
                 consequent=RuleConsequent(
                     cause_code="PRODUCT_REPUTATION_DETERIORATION",
                     causal_role="PRIMARY", support_level="CONFIRMED",
                     required_evidence=("REVIEW_RATING",),
                 )),
        ],
    ))
    impact_registry = ImpactFormulaRegistry()
    impact_registry.register(ImpactFormula(
        formula_id="est_revenue_loss", version="1.0", impact_type="REVENUE_LOSS",
        classification="ESTIMATED", unit="currency",
        expression="GMV_BASELINE * DROP_RATE",
        dependencies=("GMV_BASELINE", "DROP_RATE"),
    ))
    priority_registry = PriorityPolicyRegistry()
    priority_registry.register(PriorityPolicy(
        policy_id="commerce.priority.v1", version="1.0",
    ))
    return CompileContext(
        metric_registry=metric_registry, policy_registry=policy_registry,
        ruleset_registry=ruleset_registry, impact_registry=impact_registry,
        priority_registry=priority_registry,
    )


@pytest.fixture
def plan_registry(compile_context):
    return DiagnosticPlanRegistry(compile_context)


@pytest.fixture
def facts():
    return FakeFactQueryExecutor({
        ("SESSIONS", "store_amazon_001"): {"records": [{"value": 1000.0}]},
        ("ORDERS", "store_amazon_001"): {"records": [{"value": 20.0}]},
        ("REVIEW_RATING", "store_amazon_001"): {"records": [{"value": 3.2}]},
    })


def make_conversion_plan(required_evidence=("REVIEW_RATING",), baseline_value=0.04,
                         when=None, failure_step=None):
    """A minimal conversion-decline diagnosis plan."""
    steps = [
        StepDefinition("q_sessions", STEP_FACT_QUERY,
                       {"resource": "SESSIONS", "evidence_code": "SESSIONS"},
                       next=("q_orders",)),
        StepDefinition("q_orders", STEP_FACT_QUERY,
                       {"resource": "ORDERS", "evidence_code": "ORDERS"},
                       next=("q_review",)),
        StepDefinition("q_review", STEP_FACT_QUERY,
                       {"resource": "REVIEW_RATING", "evidence_code": "REVIEW_RATING"},
                       next=("cvr",)),
        StepDefinition("cvr", STEP_METRIC_COMPUTE,
                       {"metric": "CVR",
                        "inputs": {"ORDERS": "evidence:ORDERS",
                                   "SESSIONS": "evidence:SESSIONS"}},
                       next=("detect",)),
        StepDefinition("detect", STEP_ANOMALY_DETECT,
                       {"policy": "commerce.anomaly.v1", "metric": "CVR",
                        "baseline_value": baseline_value,
                        "signal_code": "CVR_DROP", "domain": "conversion"},
                       when=tuple(when or ()), next=("rule",)),
        StepDefinition("rule", STEP_RULE_EVALUATE,
                       {"rule_set": "commerce.conversion.v1"}, next=("assemble",)),
        StepDefinition("assemble", STEP_RESULT_ASSEMBLE, {}),
    ]
    return PlanDefinition(
        plan_id="conversion_decline_mini", version="1.0", domain="conversion",
        skill_id="store_performance_diagnosis", skill_version="1.0",
        required_evidence=tuple(required_evidence),
        steps=tuple(steps),
    )


__all__ = [
    "SUBJECT", "compile_context", "plan_registry", "facts",
    "make_conversion_plan",
]
