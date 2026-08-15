"""Core metric definitions tests: unique definitions, complete coverage."""

import pytest

from app.commerce.diagnostics import (
    build_core_metric_definitions,
    build_core_metric_registry,
)
from app.commerce.diagnostics.errors import DuplicateMetricDefinitionError
from app.commerce.domain.metrics import METRIC_CLASS_DERIVED

DERIVED_REQUIRED = {
    "AOV", "CTR", "CVR", "CPC", "ROAS", "ACOS", "AD_CVR", "DAYS_OF_SUPPLY",
    "REFUND_RATE", "ADD_TO_CART_RATE",
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


def test_registry_rejects_duplicate():
    registry = build_core_metric_registry()
    from app.commerce.domain.metrics import MetricDefinition
    with pytest.raises(DuplicateMetricDefinitionError):
        registry.register(MetricDefinition(
            metric="ROAS", metric_class=METRIC_CLASS_DERIVED, version="2.0",
            dependencies=("A", "B"), formula="A / B",
        ))


def test_core_metrics_compute_consistently():
    registry = build_core_metric_registry()
    from app.commerce.diagnostics import MetricEngine
    engine = MetricEngine(registry)
    values = {
        "IMPRESSIONS": 1000, "CLICKS": 50, "SESSIONS": 200, "ORDERS": 10,
        "GMV": 1000.0, "AD_SPEND": 100.0, "AD_SALES": 300.0, "AD_CLICKS": 40,
        "AD_ORDERS": 4, "AVAILABLE_INVENTORY": 200, "SALES_VELOCITY": 20,
        "ADD_TO_CARTS": 30, "REFUND_AMOUNT": 50.0,
    }
    assert engine.compute("ROAS", values).value == 3.0
    assert engine.compute("CTR", values).value == 0.05
    assert engine.compute("CVR", values).value == 0.05
    assert engine.compute("AOV", values).value == 100.0
    assert engine.compute("DAYS_OF_SUPPLY", values).value == 10.0
