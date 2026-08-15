"""Safety / bypass tests: no eval/exec/SQL/LLM, no arbitrary steps."""

import pytest

from app.commerce.diagnostics.errors import UnknownMetricError
from app.commerce.diagnostics.plans import (
    PlanCompiler,
    PlanValidationError,
    parse_plan,
)


def test_no_arbitrary_python_step():
    plan = {
        "plan_id": "evil", "version": "1.0", "domain": "x",
        "steps": [
            {"step_id": "s1", "type": "ARBITRARY_PYTHON",
             "params": {"code": "os.system('rm -rf /')"}},
        ],
    }
    with pytest.raises(PlanValidationError):
        parse_plan(plan)


def test_metric_name_cannot_inject_code(compile_context):
    from app.commerce.diagnostics.plans import (
        PlanDefinition,
        StepDefinition,
        STEP_METRIC_COMPUTE,
        STEP_RESULT_ASSEMBLE,
    )
    plan = PlanDefinition(
        plan_id="evil", version="1.0", domain="x",
        steps=(
            StepDefinition("m", STEP_METRIC_COMPUTE,
                           {"metric": "__import__('os')", "inputs": {}},
                           next=("a",)),
            StepDefinition("a", STEP_RESULT_ASSEMBLE, {}),
        ),
    )
    # The metric name is treated as an id, not evaluated.
    with pytest.raises(UnknownMetricError):
        PlanCompiler().compile(plan, compile_context)


def test_when_cannot_use_business_arithmetic():
    plan = {
        "plan_id": "evil", "version": "1.0", "domain": "x",
        "steps": [
            {"step_id": "s1", "type": "METRIC_COMPUTE",
             "params": {"metric": "CVR", "inputs": {}},
             "when": [{"path": "coverage", "operator": "GT", "value": 0}],
             "next": ["a"]},
            {"step_id": "a", "type": "RESULT_ASSEMBLE", "params": {}},
        ],
    }
    # coverage is allowed; but a raw business threshold is not expressible.
    assert parse_plan(plan).step("s1").when[0].path == "coverage"


def test_unsupported_operator_rejected():
    plan = {
        "plan_id": "evil", "version": "1.0", "domain": "x",
        "steps": [
            {"step_id": "s1", "type": "METRIC_COMPUTE",
             "params": {"metric": "CVR", "inputs": {}},
             "when": [{"path": "coverage", "operator": "REGEX", "value": "x"}],
             "next": ["a"]},
            {"step_id": "a", "type": "RESULT_ASSEMBLE", "params": {}},
        ],
    }
    with pytest.raises(PlanValidationError):
        parse_plan(plan)


def test_fact_query_spec_has_no_sql():
    from app.commerce.diagnostics.plans import FactQuerySpec
    from tests.commerce_diagnostic_plans.conftest import SUBJECT
    spec = FactQuerySpec(query_id="q", capability="commerce.metrics.read",
                         resource="metric", subject=SUBJECT,
                         params={"metric_name": "ORDERS"})
    assert "sql" not in spec.to_dict()
