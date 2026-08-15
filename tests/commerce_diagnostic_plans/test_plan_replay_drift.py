"""Deterministic replay + version-drift tests."""

from app.commerce.diagnostics.plans import (
    PlanDefinition,
    PlanExecutor,
    StepDefinition,
    STEP_FACT_QUERY,
    STEP_METRIC_COMPUTE,
    STEP_RESULT_ASSEMBLE,
)
from app.commerce.domain.metrics import METRIC_CLASS_DERIVED, MetricDefinition
from tests.commerce_diagnostic_plans.conftest import SUBJECT


def _roas_plan():
    return PlanDefinition(
        plan_id="roas_mini", version="1.0", domain="advertising",
        skill_id="advertising_performance_diagnosis", skill_version="1.0",
        steps=(
            StepDefinition("q_ad_sales", STEP_FACT_QUERY,
                           {"resource": "AD_SALES", "evidence_code": "AD_SALES"},
                           next=("q_ad_spend",)),
            StepDefinition("q_ad_spend", STEP_FACT_QUERY,
                           {"resource": "AD_SPEND", "evidence_code": "AD_SPEND"},
                           next=("roas",)),
            StepDefinition("roas", STEP_METRIC_COMPUTE,
                           {"metric": "ROAS",
                            "inputs": {"AD_SALES": "evidence:AD_SALES",
                                       "AD_SPEND": "evidence:AD_SPEND"}},
                           next=("assemble",)),
            StepDefinition("assemble", STEP_RESULT_ASSEMBLE, {}),
        ),
    )


def _facts():
    from app.commerce.diagnostics.plans import FakeFactQueryExecutor
    return FakeFactQueryExecutor({
        ("AD_SALES", "store_amazon_001"): {"records": [{"value": 100.0}]},
        ("AD_SPEND", "store_amazon_001"): {"records": [{"value": 30.0}]},
    })


def test_deterministic_replay(plan_registry, compile_context):
    plan_registry.register(_roas_plan())
    plan_registry.activate("roas_mini")
    ir = plan_registry.get_active_ir("roas_mini")
    executor = PlanExecutor()
    first = executor.execute(ir, compile_context, _facts(), SUBJECT)
    second = executor.execute(ir, compile_context, _facts(), SUBJECT)
    assert first.metric_value("ROAS") == second.metric_value("ROAS") == 3.3333
    assert first.outcome == second.outcome


def test_version_drift_no_replay_change(plan_registry, compile_context):
    # Register a second ROAS version with higher precision, then promote it.
    metric_registry = compile_context.metric_registry
    metric_registry.register(MetricDefinition(
        metric="ROAS", metric_class=METRIC_CLASS_DERIVED, version="2.0",
        dependencies=("AD_SALES", "AD_SPEND"), formula="AD_SALES / AD_SPEND",
        precision=6,
    ))
    plan_registry.register(_roas_plan())
    plan_registry.activate("roas_mini")
    ir = plan_registry.get_active_ir("roas_mini")
    executor = PlanExecutor()

    before = executor.execute(ir, compile_context, _facts(), SUBJECT)
    assert before.metric_value("ROAS") == 3.3333  # pinned to v1.0

    # Drift the active metric version; the compiled plan must NOT drift.
    metric_registry.activate("ROAS", "2.0")
    after = executor.execute(ir, compile_context, _facts(), SUBJECT)
    assert after.metric_value("ROAS") == 3.3333  # still v1.0, not 3.333333

    # The IR dependency is pinned.
    pinned = {d.id: d.version for d in ir.dependencies if d.kind == "metric"}
    assert pinned["ROAS"] == "1.0"
