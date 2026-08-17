"""PlanExecutor tests: execution, WHEN gating, failure policy, outcomes."""

from dataclasses import replace

import pytest

from app.commerce.diagnostics.plans import (
    FAILURE_MARK_UNKNOWN,
    FAILURE_SKIP,
    FAILURE_STOP,
    PlanExecutor,
    STEP_STATUS_FAILED,
    STEP_STATUS_MARKED_UNKNOWN,
    STEP_STATUS_SKIPPED,
    STEP_STATUS_SUCCEEDED,
    STOP_INSUFFICIENT_DATA,
    STOP_NORMAL,
    STOP_SUCCESS,
    STOP_UNSUPPORTED,
    WhenCondition,
)
from app.commerce.diagnostics.plans import StepDefinition, STEP_METRIC_COMPUTE
from tests.commerce_diagnostic_plans.conftest import SUBJECT, make_conversion_plan


def _run(plan_registry, compile_context, facts, plan=None):
    plan = plan or make_conversion_plan()
    plan_registry.register(plan)
    plan_registry.activate(plan.plan_id)
    ir = plan_registry.get_active_ir(plan.plan_id)
    return PlanExecutor().execute(ir, compile_context, facts, SUBJECT)


def test_success(plan_registry, compile_context, facts):
    state = _run(plan_registry, compile_context, facts)
    assert state.outcome == STOP_SUCCESS
    assert state.metric_value("CVR") == 0.02
    assert state.signals[0].status == "CRITICAL"
    assert state.causes[0].cause_code == "PRODUCT_REPUTATION_DETERIORATION"
    assert state.diagnostic_result.status == "COMPLETED"
    assert state.step_statuses["assemble"] == STEP_STATUS_SUCCEEDED


def test_stop_normal_no_anomaly(plan_registry, compile_context, facts):
    # baseline == current -> no anomaly -> STOP_NORMAL.
    state = _run(plan_registry, compile_context, facts,
                 plan=make_conversion_plan(baseline_value=0.02))
    assert state.outcome == STOP_NORMAL
    assert state.causes == []


def test_stop_insufficient_data_missing_required(plan_registry, compile_context, facts):
    # REVIEW_RATING required but not provided by the fact executor.
    empty = type(facts)({})
    state = _run(plan_registry, compile_context, empty)
    assert state.outcome == STOP_INSUFFICIENT_DATA
    assert "REVIEW_RATING" in state.unavailable_evidence


def test_when_gating_skips_step(plan_registry, compile_context, facts):
    # Gate ANOMALY_DETECT on a condition that never holds -> step skipped.
    plan = make_conversion_plan(
        when=(WhenCondition("signal_status.CVR_DROP", "EXISTS"),)
    )
    state = _run(plan_registry, compile_context, facts, plan=plan)
    assert state.step_statuses["detect"] == STEP_STATUS_SKIPPED
    assert state.signals == []


def test_failure_skip(plan_registry, compile_context, facts):
    plan = make_conversion_plan()
    steps = list(plan.steps)
    # A METRIC_COMPUTE with an invalid input reference raises -> SKIP (default).
    steps[3] = replace(steps[3], params={
        "metric": "CVR",
        "inputs": {"ORDERS": "bogus:ORDERS", "SESSIONS": "evidence:SESSIONS"},
    }, on_failure=FAILURE_SKIP)
    state = _run(plan_registry, compile_context, facts, plan=replace(plan, steps=tuple(steps)))
    assert state.step_statuses["cvr"] == STEP_STATUS_SKIPPED
    # Plan continues; metric value is missing so anomaly is UNKNOWN, no causes.
    assert state.errors


def test_failure_mark_unknown(plan_registry, compile_context, facts):
    plan = make_conversion_plan()
    steps = list(plan.steps)
    steps[3] = replace(steps[3], params={
        "metric": "CVR",
        "inputs": {"ORDERS": "bogus:ORDERS", "SESSIONS": "evidence:SESSIONS"},
    }, on_failure=FAILURE_MARK_UNKNOWN)
    state = _run(plan_registry, compile_context, facts, plan=replace(plan, steps=tuple(steps)))
    assert state.step_statuses["cvr"] == STEP_STATUS_MARKED_UNKNOWN


def test_failure_stop(plan_registry, compile_context, facts):
    plan = make_conversion_plan()
    steps = list(plan.steps)
    steps[3] = replace(steps[3], params={
        "metric": "CVR",
        "inputs": {"ORDERS": "bogus:ORDERS", "SESSIONS": "evidence:SESSIONS"},
    }, on_failure=FAILURE_STOP)
    state = _run(plan_registry, compile_context, facts, plan=replace(plan, steps=tuple(steps)))
    assert state.step_statuses["cvr"] == STEP_STATUS_FAILED
    assert state.outcome == STOP_UNSUPPORTED
    assert "rule" not in state.step_statuses  # halted before rule step


def test_data_quality_gate_stops_on_insufficient(plan_registry, compile_context, facts):
    from app.commerce.diagnostics.plans import (
        STEP_DATA_QUALITY_GATE,
        STEP_RESULT_ASSEMBLE,
    )
    from app.commerce.diagnostics.plans.schema import PlanDefinition
    plan = PlanDefinition(
        plan_id="quality_gate_mini", version="1.0", domain="conversion",
        required_evidence=("REVIEW_RATING",),
        steps=(
            StepDefinition("gate", STEP_DATA_QUALITY_GATE,
                           {"requirement": {"required_evidence_codes": ["REVIEW_RATING"]},
                            "stop_on_insufficient": True}, next=("assemble",)),
            StepDefinition("assemble", STEP_RESULT_ASSEMBLE, {}),
        ),
    )
    empty = type(facts)({})
    state = _run(plan_registry, compile_context, empty, plan=plan)
    assert state.outcome == STOP_INSUFFICIENT_DATA
    assert state.data_quality.status == "INSUFFICIENT"
