"""Mini deterministic chain: metrics -> comparison -> signal -> cause -> impact
-> priority, wired end-to-end without any LLM."""

from app.commerce.contracts.evidence import Evidence
from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics import (
    AnomalyEngine,
    ComparisonEngine,
    ImpactEngine,
    ImpactFormula,
    MetricEngine,
    PriorityEngine,
    PriorityFactors,
    PriorityPolicy,
    Rule,
    RuleCondition,
    RuleConsequent,
    RuleEngine,
    RuleSet,
    build_core_metric_registry,
)
from app.commerce.diagnostics.definitions.policies import DiagnosticPolicy

SUBJECT = SubjectRef("STORE", "store_amazon_001")

POLICY = DiagnosticPolicy(policy_id="commerce.anomaly.v1", version="1.0",
                          min_baseline_volume=0.0001, min_sample_size=3)

RULE_SET = RuleSet(
    rule_set_id="commerce.conversion.v1", version="1.0", domain="conversion",
    rules=[
        Rule(
            rule_id="cvr_drop_review", version="1.0",
            antecedents=[RuleCondition("CVR_DROP", "ABNORMAL", "DOWN")],
            consequent=RuleConsequent(
                cause_code="PRODUCT_REPUTATION_DETERIORATION",
                causal_role="PRIMARY", support_level="CONFIRMED",
                required_evidence=("REVIEW_RATING",),
            ),
        )
    ],
)

IMPACT_FORMULA = ImpactFormula(
    formula_id="est_revenue_loss", version="1.0", impact_type="ESTIMATED",
    classification="REVENUE_LOSS", unit="currency",
    expression="GMV_BASELINE * DROP_RATE", dependencies=("GMV_BASELINE", "DROP_RATE"),
)

PRIORITY_POLICY = PriorityPolicy(policy_id="commerce.priority.v1", version="1.0")

FACTORS = PriorityFactors(severity=0.9, business_impact=0.8, urgency=0.7,
                          confidence=0.8, actionability=0.7)


def _run_chain():
    metric_engine = MetricEngine(build_core_metric_registry())

    # 1. Facts: current and baseline conversion rates (DERIVED via MetricEngine).
    current_cvr = metric_engine.compute("CVR", {"ORDERS": 20, "SESSIONS": 1000}).value
    baseline_cvr = metric_engine.compute("CVR", {"ORDERS": 40, "SESSIONS": 1000}).value

    # 2. Comparison.
    comparison = ComparisonEngine().compare(current_cvr, baseline_cvr)

    # 3. Anomaly -> Signal.
    signal = AnomalyEngine().detect(
        subject=SUBJECT, signal_code="CVR_DROP", domain="conversion",
        current_value=current_cvr, baseline_value=baseline_cvr,
        baseline_series=[0.04, 0.041, 0.039, 0.04, 0.04], policy=POLICY,
    )

    # 4. Rule -> Cause.
    review_evidence = Evidence(
        evidence_id="ev_review", subject=SUBJECT, evidence_type="METRIC",
        code="REVIEW_RATING", value=3.2,
    )
    causes = RuleEngine().evaluate(
        signals=[signal], evidence=[review_evidence], rule_set=RULE_SET, subject=SUBJECT,
    )

    # 5. Impact -> estimated revenue loss.
    impact = ImpactEngine().compute(
        IMPACT_FORMULA,
        {"GMV_BASELINE": 100000.0, "DROP_RATE": abs(comparison.relative_change)},
        subject=SUBJECT,
    )

    # 6. Priority.
    priority = PriorityEngine().compute(FACTORS, PRIORITY_POLICY)

    return comparison, signal, causes[0], impact, priority


def test_mini_chain_end_to_end():
    comparison, signal, cause, impact, priority = _run_chain()

    assert comparison.current_value == 0.02
    assert comparison.baseline_value == 0.04
    assert comparison.relative_change == -0.5

    assert signal.status in ("ABNORMAL", "CRITICAL")
    assert signal.direction == "DOWN"

    assert cause.cause_code == "PRODUCT_REPUTATION_DETERIORATION"
    assert cause.causal_role == "PRIMARY"
    assert cause.support_level == "CONFIRMED"

    assert impact.impact_type == "ESTIMATED"
    assert impact.value == 50000.0

    assert priority.level in ("P0", "P1")


def test_mini_chain_deterministic_business_outputs():
    first = _run_chain()
    second = _run_chain()
    # Business-relevant outputs are deterministic (ids are generated per run).
    assert first[0] == second[0]                       # comparison
    assert first[1].status == second[1].status         # signal status
    assert first[1].direction == second[1].direction
    assert first[2].cause_code == second[2].cause_code
    assert first[2].causal_role == second[2].causal_role
    assert first[3].value == second[3].value           # impact value
    assert first[4].level == second[4].level           # priority level
