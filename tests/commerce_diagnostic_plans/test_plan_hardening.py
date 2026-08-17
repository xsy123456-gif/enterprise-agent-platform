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
    SecurityFieldViolation,
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


# ── Reserved security fields / trusted context ──────────────

def test_reserved_security_field_rejected():
    plan = make_conversion_plan()
    steps = list(plan.steps)
    steps[0] = replace(steps[0], params={
        "capability": CAP_METRICS, "resource": "SESSIONS",
        "evidence_code": "SESSIONS", "tenant_id": "evil_tenant",
    })
    with pytest.raises(SecurityFieldViolation):
        parse_plan(replace(plan, steps=tuple(steps)).to_dict())


def test_reserved_security_field_rejected_nested():
    plan = make_conversion_plan()
    steps = list(plan.steps)
    steps[0] = replace(steps[0], params={
        "capability": CAP_METRICS, "resource": "SESSIONS",
        "evidence_code": "SESSIONS",
        "query_params": {"filters": [{"scopes": ["evil"]}]},
    })
    with pytest.raises(SecurityFieldViolation):
        parse_plan(replace(plan, steps=tuple(steps)).to_dict())


def test_fact_executor_receives_only_trusted_context(plan_registry, compile_context):
    plan = make_conversion_plan()
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
    # The fake only ever saw the injected trusted context, never a plan-derived tenant.
    assert executor.last_trusted_context.tenant_id == "company_A"
    assert executor.last_trusted_context.principal_id == "trusted_user"


def test_trusted_context_is_immutable():
    from dataclasses import FrozenInstanceError
    trusted = TrustedExecutionContext(tenant_id="company_A")
    with pytest.raises(FrozenInstanceError):
        trusted.tenant_id = "evil"


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


# ── Timezone-aware period resolution ────────────────────────

def test_naive_datetime_rejected():
    from datetime import datetime
    from app.commerce.diagnostics.plans import resolve_period
    with pytest.raises(ValueError):
        resolve_period({"days": 7}, datetime(2026, 8, 10, 0, 0, 0))


def test_naive_iso_string_rejected():
    from app.commerce.diagnostics.plans import resolve_period
    with pytest.raises(ValueError):
        resolve_period({"days": 7}, "2026-08-10T00:00:00")


def test_resolved_period_preserves_timezone_and_boundary():
    from app.commerce.diagnostics.plans import resolve_period
    result = resolve_period({"days": 7, "timezone": "America/New_York",
                             "boundary_policy": "EXCLUSIVE"},
                            "2026-08-10T00:00:00+00:00")
    assert result.timezone == "America/New_York"
    assert result.boundary_policy == "EXCLUSIVE"
    assert result.start.endswith("+00:00")


def test_explicit_naive_window_rejected():
    from app.commerce.diagnostics.plans import resolve_period
    with pytest.raises(ValueError):
        resolve_period({"start": "2026-08-01T00:00:00", "end": "2026-08-08T00:00:00"}, None)


# ── Runtime edge/step activation (false branch + merge) ─────

def test_false_branch_descendants_not_executed(plan_registry, compile_context):
    from app.commerce.diagnostics.plans import WhenCondition, STEP_STATUS_SKIPPED
    plan = make_conversion_plan(when=(WhenCondition("signal_status.CVR_DROP", "EXISTS"),))
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
    assert state.step_statuses["detect"] == STEP_STATUS_SKIPPED
    # Downstream of the false branch is never activated, so never executes.
    assert state.step_statuses["rule"] == STEP_STATUS_SKIPPED
    assert state.step_statuses["assemble"] == STEP_STATUS_SKIPPED
    assert state.diagnostic_result is None


def test_branch_merge_executes_via_active_branch(plan_registry, compile_context):
    from app.commerce.diagnostics.plans import (
        STEP_STATUS_SKIPPED, STEP_STATUS_SUCCEEDED, WhenCondition,
    )
    plan = PlanDefinition(
        plan_id="branch_merge_mini", version="1.0", domain="conversion",
        required_capabilities=(CAP_METRICS,),
        steps=(
            StepDefinition("start", STEP_FACT_QUERY,
                           {"capability": CAP_METRICS, "resource": "SESSIONS",
                            "evidence_code": "SESSIONS"}, next=("left", "right")),
            StepDefinition("left", STEP_FACT_QUERY,
                           {"capability": CAP_METRICS, "resource": "ORDERS",
                            "evidence_code": "ORDERS"}, next=("assemble",)),
            StepDefinition("right", STEP_FACT_QUERY,
                           {"capability": CAP_METRICS, "resource": "REVIEW_RATING",
                            "evidence_code": "REVIEW_RATING"},
                           when=(WhenCondition("has_signal.CVR_DROP", "EXISTS"),),
                           next=("assemble",)),
            StepDefinition("assemble", STEP_RESULT_ASSEMBLE, {}),
        ),
    )
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
    assert state.step_statuses["right"] == STEP_STATUS_SKIPPED
    # The merge step executes via the active "left" branch.
    assert state.step_statuses["assemble"] == STEP_STATUS_SUCCEEDED
    assert state.diagnostic_result is not None


def test_explicit_entry_step_id(plan_registry, compile_context):
    plan = make_conversion_plan()
    plan = replace(plan, entry_step_id="q_sessions")
    plan_registry.register(plan)
    plan_registry.activate(plan.plan_id)
    assert plan_registry.get_active_ir(plan.plan_id).entry_step_id == "q_sessions"
