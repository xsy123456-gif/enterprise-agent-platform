"""Core metric definitions tests: unique definitions, complete coverage."""

import pytest

from app.commerce.diagnostics import (
    MetricEngine,
    build_core_metric_definitions,
    build_core_metric_registry,
)
from app.commerce.diagnostics.errors import DuplicateMetricDefinitionError
from app.commerce.domain.metrics import (
    METRIC_CLASS_DERIVED,
    METRIC_CLASS_SOURCE,
    MetricDefinition,
)

DERIVED_REQUIRED = {
    "AOV", "CTR", "CVR", "CPC", "ROAS", "ACOS", "AD_CVR", "DAYS_OF_SUPPLY",
    "REFUND_RATE", "ADD_TO_CART_RATE", "SALES_VELOCITY",
}


def test_core_definitions_have_unique_names():
    definitions = build_core_metric_definitions()
    names = [d.metric for d in definitions]
    assert len(names) == len(set(names))


def test_required_derived_metrics_present():
    registry = build_core_metric_registry()
    derived = {
        d.metric for d in registry.list_definitions()
        if d.metric_class == METRIC_CLASS_DERIVED
    }
    assert DERIVED_REQUIRED <= derived


def test_every_derived_has_formula_and_dependencies():
    registry = build_core_metric_registry()
    for definition in registry.list_definitions():
        if definition.metric_class == METRIC_CLASS_DERIVED:
            assert definition.formula
            assert definition.dependencies


def test_registry_rejects_duplicate_same_version():
    registry = build_core_metric_registry()
    with pytest.raises(DuplicateMetricDefinitionError):
        registry.register(MetricDefinition(
            metric="ROAS", metric_class=METRIC_CLASS_DERIVED, version="1.0",
            dependencies=("A", "B"), formula="A / B",
        ))


def test_core_metrics_compute_consistently():
    registry = build_core_metric_registry()
    engine = MetricEngine(registry)
    values = {
        "IMPRESSIONS": 1000, "CLICKS": 50, "SESSIONS": 200, "ORDERS": 10,
        "GMV": 1000.0, "AD_SPEND": 100.0, "AD_SALES": 300.0, "AD_CLICKS": 40,
        "AD_ORDERS": 4, "AVAILABLE_INVENTORY": 200, "UNITS": 200, "PERIOD_DAYS": 10,
        "ADD_TO_CARTS": 30, "REFUND_AMOUNT": 50.0,
    }
    assert engine.compute("ROAS", values).value == 3.0
    assert engine.compute("CTR", values).value == 0.05
    assert engine.compute("CVR", values).value == 0.05
    assert engine.compute("AOV", values).value == 100.0
    # SALES_VELOCITY = UNITS / PERIOD_DAYS = 20 units/day; DOS = 200 / 20 = 10.
    assert engine.compute("DAYS_OF_SUPPLY", values).value == 10.0


def test_sales_velocity_is_derived_not_source():
    registry = build_core_metric_registry()
    assert registry.get("SALES_VELOCITY").metric_class == METRIC_CLASS_DERIVED
    assert registry.get("SALES_VELOCITY").formula == "UNITS / PERIOD_DAYS"


def test_sales_velocity_no_hardcoded_window():
    registry = build_core_metric_registry()
    engine = MetricEngine(registry)
    short = engine.compute("SALES_VELOCITY", {"UNITS": 100, "PERIOD_DAYS": 5})
    long = engine.compute("SALES_VELOCITY", {"UNITS": 100, "PERIOD_DAYS": 25})
    assert short.value == 20.0
    assert long.value == 4.0


def test_days_of_supply_via_sales_velocity():
    registry = build_core_metric_registry()
    engine = MetricEngine(registry)
    result = engine.compute(
        "DAYS_OF_SUPPLY",
        {"AVAILABLE_INVENTORY": 300, "UNITS": 100, "PERIOD_DAYS": 10},
    )
    assert result.value == 30.0
    assert set(result.dependencies_used) == {"AVAILABLE_INVENTORY", "UNITS", "PERIOD_DAYS"}
