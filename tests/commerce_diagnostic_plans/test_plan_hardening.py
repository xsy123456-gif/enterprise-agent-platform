"""Phase 5 gate hardening tests: capability, trusted context, max-depth,
quality gate, reachability, period resolution."""

from dataclasses import replace

import pytest

from app.commerce.contracts.query import TimeRange
from app.commerce.diagnostics.plans import (
    FakeFactQueryExecutor,
    MaxDepthExceededError,
    PlanDefinition,
    PlanExecutor,
    PlanValidationError,
    StepDefinition,
    STEP_DATA_QUALITY_GATE,
    STEP_FACT_QUERY,
    STEP_METRIC_COMPUTE,
    STEP_RESULT_ASSEMBLE,
    STOP_INSUFFICIENT_DATA,
    TrustedExecutionContext,
    parse_plan,
)
from tests.commerce_diagnostic_plans.conftest import (
    CAP_METRICS,
    SUBJECT,
    make_conversion_plan,
)


# ── Capability contract ─────────────────────────────────────

def test_capability_mismatch_rejected():
    plan = make_conversion_plan(required_capabilities=("commerce.review.read",))
    with pytest.raises(PlanValidationError):
        parse_plan(plan.to_dict())


def test_fact_query_requires_capability():
    plan = make_conversion_plan()
    steps = list(plan.steps)
    steps[0] = replace(steps[0], params={"resource": "SESSIONS"})  # no capability
    with pytest.raises(PlanValidationError):
        parse_plan(replace(plan, steps=tuple(steps)).to_dict())


# ── Trusted context injection ───────────────────────────────

def test_request_cannot_override_trusted_context(plan_registry, compile_context):
    plan = make_conversion_plan()
    # Try to smuggle tenant/principal through step params and query_params.
    steps = list(plan.steps)
    steps[0] = replace(steps[0], params={
        "capability": CAP_METRICS, "resource": "SESSIONS",
        "evidence_code": "SESSIONS",
        "tenant_id": "evil_tenant", "query_params": {"principal_id": "evil_user"},
    })
    plan = replace(plan, steps=tuple(steps))
    plan_registry.register(plan)
    plan_registry.activate(plan.plan_id)

    executor = FakeFactQueryExecutor({
        (CAP_METRICS, "SESSIONS", "store_amazon_001"): {"records": [{"value": 1000.0}]},
        (CAP_METRICS, "ORDERS", "store_amazon_001"): {"records": [{"value": 20.0}]},
        (CAP_METRICS, "REVIEW_RATING", "store_amazon_001"): {"records": [{"value": 3.2}]},
    })
    trusted = TrustedExecutionContext(tenant_id="company_A", principal_id="trusted_user")
    PlanExecutor().execute(plan_registry.get_active_ir(plan.plan_id), compile_context,
                           executor, SUBJECT, trusted_context=trusted)
    # The fake only ever saw the injected trusted context.
    assert executor.last_trusted_context.tenant_id == "company_A"
    assert executor.last_trusted_context.principal_id == "trusted_user"


# ── max_depth enforcement ───────────────────────────────────

def test_max_depth_exceeded_rejected():
    plan = make_conversion_plan()
    steps = list(plan.steps)
    steps[0] = replace(steps[0], params={
        "capability": CAP_METRICS, "resource": "SESSIONS",
        "evidence_code": "SESSIONS", "drill_depth": 4,
    })
    # default max_depth is 3, drill_depth 4 exceeds it.
    with pytest.raises(MaxDepthExceededError):
        parse_plan(replace(plan, steps=tuple(steps)).to_dict())


def test_drill_depth_tracked_at_runtime(plan_registry, compile_context):
    plan = make_conversion_plan()
    plan_registry.register(plan)
    plan_registry.activate(plan.plan_id)
    executor = FakeFactQueryExecutor({
        (CAP_METRICS, "SESSIONS", "store_amazon_001"): {"records": [{"value": 1000.0}]},
        (CAP_METRICS, "ORDERS", "store_amazon_001"): {"records": [{"value": 20.0}]},
        (CAP_METRICS, "REVIEW_RATING", "store_amazon_001"): {"records": [{"value": 3.2}]},
    })
    state = PlanExecutor().execute(plan_registry.get_active_ir(plan.plan_id),
                                   compile_context, executor, SUBJECT,
                                   trusted_context=TrustedExecutionContext(tenant_id="company_A"))
    assert state.max_drill_depth == 1


# ── DataQualityGate extension ───────────────────────────────

def _gate_plan(requirement):
    return PlanDefinition(
        plan_id="gate_mini", version="1.0", domain="conversion",
        required_capabilities=(CAP_METRICS,),
        steps=(
            StepDefinition("q", STEP_FACT_QUERY,
                           {"capability": CAP_METRICS, "resource": "REVIEW_RATING",
                            "evidence_code": "REVIEW_RATING"}, next=("gate",)),
            StepDefinition("gate", STEP_DATA_QUALITY_GATE,
                           {"requirement": requirement, "stop_on_insufficient": True},
                           next=("assemble",)),
            StepDefinition("assemble", STEP_RESULT_ASSEMBLE, {}),
        ),
    )


def test_gate_rejects_stale_evidence(plan_registry, compile_context):
    plan = _gate_plan({"required_evidence_codes": ["REVIEW_RATING"],
                       "unacceptable_evidence_qualities": ["STALE"]})
    plan_registry.register(plan)
    plan_registry.activate(plan.plan_id)
    executor = FakeFactQueryExecutor({
        (CAP_METRICS, "REVIEW_RATING", "store_amazon_001"): {"records": [{"value": 3.2}], "quality": "STALE"},
    })
    state = PlanExecutor().execute(plan_registry.get_active_ir(plan.plan_id),
                                   compile_context, executor, SUBJECT,
                                   trusted_context=TrustedExecutionContext(tenant_id="company_A"))
    assert state.outcome == STOP_INSUFFICIENT_DATA
    assert state.data_quality.status == "INSUFFICIENT"


def test_gate_rejects_stale_freshness(plan_registry, compile_context):
    plan = _gate_plan({"required_evidence_codes": ["REVIEW_RATING"],
                       "unacceptable_freshness": ["STALE"]})
    plan_registry.register(plan)
    plan_registry.activate(plan.plan_id)
    executor = FakeFactQueryExecutor({
        (CAP_METRICS, "REVIEW_RATING", "store_amazon_001"): {"records": [{"value": 3.2}], "freshness": "STALE"},
    })
    state = PlanExecutor().execute(plan_registry.get_active_ir(plan.plan_id),
                                   compile_context, executor, SUBJECT,
                                   trusted_context=TrustedExecutionContext(tenant_id="company_A"))
    assert state.outcome == STOP_INSUFFICIENT_DATA


def test_gate_rejects_insufficient_metric(plan_registry, compile_context):
    plan = PlanDefinition(
        plan_id="gate_metric_mini", version="1.0", domain="conversion",
        required_capabilities=(CAP_METRICS,),
        steps=(
            StepDefinition("q", STEP_FACT_QUERY,
                           {"capability": CAP_METRICS, "resource": "ORDERS",
                            "evidence_code": "ORDERS"}, next=("cvr",)),
            StepDefinition("cvr", STEP_METRIC_COMPUTE,
                           {"metric": "CVR", "inputs": {"ORDERS": "evidence:ORDERS"}},
                           next=("gate",)),
            StepDefinition("gate", STEP_DATA_QUALITY_GATE,
                           {"requirement": {"unacceptable_metric_statuses": ["INSUFFICIENT"]},
                            "stop_on_insufficient": True},
                           next=("assemble",)),
            StepDefinition("assemble", STEP_RESULT_ASSEMBLE, {}),
        ),
    )
    plan_registry.register(plan)
    plan_registry.activate(plan.plan_id)
    # Missing SESSIONS -> CVR is INSUFFICIENT -> gate fails.
    executor = FakeFactQueryExecutor({
        (CAP_METRICS, "ORDERS", "store_amazon_001"): {"records": [{"value": 20.0}]},
    })
    state = PlanExecutor().execute(plan_registry.get_active_ir(plan.plan_id),
                                   compile_context, executor, SUBJECT,
                                   trusted_context=TrustedExecutionContext(tenant_id="company_A"))
    assert state.outcome == STOP_INSUFFICIENT_DATA


# ── DAG reachability ────────────────────────────────────────

def test_unreachable_branch_not_executed(plan_registry, compile_context):
    plan = make_conversion_plan()
    # A dead METRIC_COMPUTE step not referenced by any next edge.
    steps = list(plan.steps) + [
        StepDefinition("dead", STEP_METRIC_COMPUTE,
                       {"metric": "AOV", "inputs": {}}),
    ]
    plan = replace(plan, steps=tuple(steps))
    plan_registry.register(plan)
    plan_registry.activate(plan.plan_id)
    executor = FakeFactQueryExecutor({
        (CAP_METRICS, "SESSIONS", "store_amazon_001"): {"records": [{"value": 1000.0}]},
        (CAP_METRICS, "ORDERS", "store_amazon_001"): {"records": [{"value": 20.0}]},
        (CAP_METRICS, "REVIEW_RATING", "store_amazon_001"): {"records": [{"value": 3.2}]},
    })
    state = PlanExecutor().execute(plan_registry.get_active_ir(plan.plan_id),
                                   compile_context, executor, SUBJECT,
                                   trusted_context=TrustedExecutionContext(tenant_id="company_A"))
    assert "AOV" not in state.metric_results  # dead step never ran


# ── Period definition vs runtime period ─────────────────────

def test_relative_period_resolved_at_runtime(plan_registry, compile_context):
    plan = replace(make_conversion_plan(), analysis_period={"days": 7})
    plan_registry.register(plan)
    plan_registry.activate(plan.plan_id)
    ir = plan_registry.get_active_ir(plan.plan_id)
    executor = FakeFactQueryExecutor({
        (CAP_METRICS, "SESSIONS", "store_amazon_001"): {"records": [{"value": 1000.0}]},
        (CAP_METRICS, "ORDERS", "store_amazon_001"): {"records": [{"value": 20.0}]},
        (CAP_METRICS, "REVIEW_RATING", "store_amazon_001"): {"records": [{"value": 3.2}]},
    })
    state = PlanExecutor().execute(ir, compile_context, executor, SUBJECT,
                                   trusted_context=TrustedExecutionContext(tenant_id="company_A"),
                                   now="2026-08-10T00:00:00+00:00")
    assert isinstance(state.analysis_period, TimeRange)
    assert state.analysis_period.start.startswith("2026-08-03")
    assert state.analysis_period.end.startswith("2026-08-10")


def test_period_spec_does_not_freeze_runtime_dates(plan_registry, compile_context):
    plan = replace(make_conversion_plan(), analysis_period={"days": 7})
    plan_registry.register(plan)
    plan_registry.activate(plan.plan_id)
    ir = plan_registry.get_active_ir(plan.plan_id)
    checksum = ir.checksum
    executor = FakeFactQueryExecutor({
        (CAP_METRICS, "SESSIONS", "store_amazon_001"): {"records": [{"value": 1000.0}]},
        (CAP_METRICS, "ORDERS", "store_amazon_001"): {"records": [{"value": 20.0}]},
        (CAP_METRICS, "REVIEW_RATING", "store_amazon_001"): {"records": [{"value": 3.2}]},
    })
    trusted = TrustedExecutionContext(tenant_id="company_A")
    s1 = PlanExecutor().execute(ir, compile_context, executor, SUBJECT,
                                trusted_context=trusted, now="2026-08-10T00:00:00+00:00")
    s2 = PlanExecutor().execute(ir, compile_context, executor, SUBJECT,
                                trusted_context=trusted, now="2026-09-01T00:00:00+00:00")
    # Same plan version -> same checksum regardless of runtime date ...
    assert s1.checksum == s2.checksum == checksum
    # ... but the resolved analysis period differs per runtime date.
    assert s1.analysis_period != s2.analysis_period
