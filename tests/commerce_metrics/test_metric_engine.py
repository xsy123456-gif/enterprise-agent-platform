"""MetricEngine tests: derived computation, zero policy, precision, deps."""

import pytest

from app.commerce.diagnostics import (
    METRIC_STATUS_INSUFFICIENT,
    MetricEngine,
    build_core_metric_registry,
)
from app.commerce.diagnostics.errors import MetricDefinitionError
from app.commerce.diagnostics.registry.metric_registry import MetricDefinitionRegistry
from app.commerce.domain.metrics import (
    METRIC_CLASS_DERIVED,
    METRIC_CLASS_SOURCE,
    MetricDefinition,
)


@pytest.fixture
def engine():
    return MetricEngine(build_core_metric_registry())


def test_compute_roas(engine):
    result = engine.compute("ROAS", {"AD_SALES": 100.0, "AD_SPEND": 50.0})
    assert result.value == 2.0
    assert result.version == "1.0"
    assert result.dependencies_used == ("AD_SALES", "AD_SPEND")


def test_compute_core_metrics(engine):
    assert engine.compute("CTR", {"CLICKS": 5, "IMPRESSIONS": 1000}).value == 0.005
    assert engine.compute("CVR", {"ORDERS": 3, "SESSIONS": 100}).value == 0.03
    assert engine.compute("CPC", {"AD_SPEND": 100.0, "CLICKS": 50}).value == 2.0
    assert engine.compute("ACOS", {"AD_SPEND": 50.0, "AD_SALES": 100.0}).value == 0.5
    assert engine.compute("AOV", {"GMV": 1000.0, "ORDERS": 40}).value == 25.0
    assert engine.compute(
        "DAYS_OF_SUPPLY",
        {"AVAILABLE_INVENTORY": 300, "UNITS": 100, "PERIOD_DAYS": 10},
    ).value == 30.0


def test_precision_rounding(engine):
    result = engine.compute("ROAS", {"AD_SALES": 100.0, "AD_SPEND": 30.0})
    assert result.value == 3.3333


def test_zero_policy_null_default(engine):
    result = engine.compute("ROAS", {"AD_SALES": 100.0, "AD_SPEND": 0.0})
    assert result.value is None
    assert result.zero_policy_applied is True


def test_zero_policy_zero():
    registry = MetricDefinitionRegistry()
    registry.register(MetricDefinition(metric="A", metric_class=METRIC_CLASS_SOURCE,
                                       version="1.0"))
    registry.register(MetricDefinition(metric="B", metric_class=METRIC_CLASS_SOURCE,
                                       version="1.0"))
    registry.register(MetricDefinition(
        metric="RATE", metric_class=METRIC_CLASS_DERIVED, version="1.0",
        dependencies=("A", "B"), formula="A / B", zero_policy="ZERO",
    ))
    engine = MetricEngine(registry)
    result = engine.compute("RATE", {"A": 5.0, "B": 0.0})
    assert result.value == 0.0
    assert result.zero_policy_applied is True


def test_missing_dependency_value(engine):
    result = engine.compute("ROAS", {"AD_SALES": 100.0})
    assert result.status == METRIC_STATUS_INSUFFICIENT
    assert result.value is None
    assert result.missing_dependencies == ("AD_SPEND",)


def test_none_dependency_value(engine):
    result = engine.compute("ROAS", {"AD_SALES": 100.0, "AD_SPEND": None})
    assert result.status == METRIC_STATUS_INSUFFICIENT
    assert result.value is None
    assert result.missing_dependencies == ("AD_SPEND",)


def test_non_derived_metric_rejected(engine):
    with pytest.raises(MetricDefinitionError):
        engine.compute("GMV", {"GMV": 100.0})


def test_nested_derived_computation():
    registry = MetricDefinitionRegistry()
    registry.register(MetricDefinition(metric="X", metric_class=METRIC_CLASS_SOURCE,
                                       version="1.0"))
    registry.register(MetricDefinition(metric="Y", metric_class=METRIC_CLASS_SOURCE,
                                       version="1.0"))
    registry.register(MetricDefinition(
        metric="A", metric_class=METRIC_CLASS_DERIVED, version="1.0",
        dependencies=("X", "Y"), formula="X / Y",
    ))
    registry.register(MetricDefinition(
        metric="B", metric_class=METRIC_CLASS_DERIVED, version="1.0",
        dependencies=("A",), formula="A * 2", dependency_versions={"A": "1.0"},
    ))
    engine = MetricEngine(registry)
    result = engine.compute("B", {"X": 10.0, "Y": 2.0})
    assert result.value == 10.0
    assert result.dependencies_used == ("X", "Y")


def test_deterministic_same_input_same_version(engine):
    values = {"AD_SALES": 100.0, "AD_SPEND": 30.0}
    first = engine.compute("ROAS", values)
    second = engine.compute("ROAS", values)
    assert first == second


def test_dependencies_used_are_leaves(engine):
    result = engine.compute("ROAS", {"AD_SALES": 100.0, "AD_SPEND": 50.0})
    assert set(result.dependencies_used) == {"AD_SALES", "AD_SPEND"}
