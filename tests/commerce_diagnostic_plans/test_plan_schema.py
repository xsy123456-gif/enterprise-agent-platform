"""Validator / compiler / checksum tests."""

import pytest

from app.commerce.diagnostics.plans import (
    PlanCompiler,
    PlanValidationError,
    StepDefinition,
    STEP_FACT_QUERY,
    STEP_METRIC_COMPUTE,
    STEP_RESULT_ASSEMBLE,
    parse_plan,
)
from tests.commerce_diagnostic_plans.conftest import make_conversion_plan


def test_parse_and_validate_valid_plan():
    definition = parse_plan(make_conversion_plan().to_dict())
    assert definition.plan_id == "conversion_decline_mini"


def test_reject_unknown_step_type():
    plan = make_conversion_plan()
    steps = list(plan.steps) + [
        StepDefinition("evil", "ARBITRARY_PYTHON", {"code": "os.system('x')"}),
    ]
    from dataclasses import replace
    with pytest.raises(PlanValidationError):
        parse_plan(replace(plan, steps=tuple(steps)).to_dict())


def test_reject_cycle():
    from dataclasses import replace
    plan = make_conversion_plan()
    steps = list(plan.steps)
    steps[0] = replace(steps[0], next=("assemble",))
    steps[-1] = replace(steps[-1], next=("q_sessions",))
    with pytest.raises(PlanValidationError):
        parse_plan(replace(plan, steps=tuple(steps)).to_dict())


def test_reject_unknown_next_ref():
    from dataclasses import replace
    plan = make_conversion_plan()
    steps = list(plan.steps)
    steps[0] = replace(steps[0], next=("does_not_exist",))
    with pytest.raises(PlanValidationError):
        parse_plan(replace(plan, steps=tuple(steps)).to_dict())


def test_reject_unsupported_when_path():
    from dataclasses import replace
    from app.commerce.diagnostics.plans import WhenCondition
    plan = make_conversion_plan()
    steps = list(plan.steps)
    steps[4] = replace(steps[4], when=(WhenCondition("cvr < -0.2", "EQ", True),))
    with pytest.raises(PlanValidationError):
        parse_plan(replace(plan, steps=tuple(steps)).to_dict())


def test_reject_no_result_assemble():
    from dataclasses import replace
    plan = make_conversion_plan()
    steps = [s for s in plan.steps if s.type != STEP_RESULT_ASSEMBLE]
    with pytest.raises(PlanValidationError):
        parse_plan(replace(plan, steps=tuple(steps)).to_dict())


def test_compiler_pins_versions(compile_context):
    ir = PlanCompiler().compile(make_conversion_plan(), compile_context)
    by_kind = {(d.kind, d.id): d.version for d in ir.dependencies}
    assert by_kind[("metric", "CVR")] == "1.0"
    assert by_kind[("policy", "commerce.anomaly.v1")] == "1.0"
    assert by_kind[("ruleset", "commerce.conversion.v1")] == "1.0"


def test_checksum_deterministic(compile_context):
    compiler = PlanCompiler()
    a = compiler.compile(make_conversion_plan(), compile_context)
    b = compiler.compile(make_conversion_plan(), compile_context)
    assert a.checksum == b.checksum
    assert a.checksum


def test_checksum_changes_with_plan(compile_context):
    compiler = PlanCompiler()
    a = compiler.compile(make_conversion_plan(), compile_context)
    from dataclasses import replace
    b = compiler.compile(replace(make_conversion_plan(), version="2.0"), compile_context)
    assert a.checksum != b.checksum


def test_compile_unknown_version_fails_closed(compile_context):
    from dataclasses import replace
    plan = make_conversion_plan()
    steps = list(plan.steps)
    steps[3] = replace(steps[3], params={"metric": "CVR@9.9",
                                         "inputs": {"ORDERS": "evidence:ORDERS",
                                                    "SESSIONS": "evidence:SESSIONS"}})
    from app.commerce.diagnostics.errors import UnknownMetricVersionError
    with pytest.raises(UnknownMetricVersionError):
        PlanCompiler().compile(replace(plan, steps=tuple(steps)), compile_context)
