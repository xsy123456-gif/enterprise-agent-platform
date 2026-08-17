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
    TrustedExecutionContext,
)

SUBJECT = SubjectRef("STORE", "store_amazon_001")
CAP_METRICS = "commerce.metrics.read"
TRUSTED_CONTEXT = TrustedExecutionContext(
    tenant_id="company_A", principal_id="user_001", organization_id="org_A",
    scopes=("store_amazon_001",), trace_id="trace-1", execution_id="exec-1",
)


@pytest.fixture
def trusted_context():
    return TRUSTED_CONTEXT


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
        (CAP_METRICS, "SESSIONS", "store_amazon_001"): {"records": [{"value": 1000.0}]},
        (CAP_METRICS, "ORDERS", "store_amazon_001"): {"records": [{"value": 20.0}]},
        (CAP_METRICS, "REVIEW_RATING", "store_amazon_001"): {"records": [{"value": 3.2}]},
    })


def _fact_step(step_id, code, next_ids, capability=CAP_METRICS, **extra):
    params = {"capability": capability, "resource": code, "evidence_code": code}
    params.update(extra)
    return StepDefinition(step_id, STEP_FACT_QUERY, params, next=tuple(next_ids))


def make_conversion_plan(required_evidence=("REVIEW_RATING",), baseline_value=0.04,
                         when=None, required_capabilities=(CAP_METRICS,)):
    """A minimal conversion-decline diagnosis plan."""
    steps = [
        _fact_step("q_sessions", "SESSIONS", ("q_orders",)),
        _fact_step("q_orders", "ORDERS", ("q_review",)),
        _fact_step("q_review", "REVIEW_RATING", ("cvr",)),
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
        required_capabilities=tuple(required_capabilities),
        required_evidence=tuple(required_evidence),
        steps=tuple(steps),
    )


__all__ = [
    "SUBJECT", "CAP_METRICS", "TRUSTED_CONTEXT", "compile_context",
    "plan_registry", "facts", "trusted_context", "make_conversion_plan",
]
