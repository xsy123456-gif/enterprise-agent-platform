"""MetricDefinitionRegistry tests: one formula per metric, validation."""

import pytest

from app.commerce.diagnostics.errors import (
    DuplicateMetricDefinitionError,
    MetricDefinitionError,
    UnknownMetricError,
    UnknownMetricVersionError,
)
from app.commerce.diagnostics.registry.metric_registry import (
    MetricDefinitionRegistry,
)
from app.commerce.domain.metrics import (
    METRIC_CLASS_DERIVED,
    METRIC_CLASS_SOURCE,
    MetricDefinition,
)


def _derived(metric, deps, formula):
    return MetricDefinition(
        metric=metric, metric_class=METRIC_CLASS_DERIVED, version="1.0",
        dependencies=tuple(deps), formula=formula,
    )


def test_register_and_get():
    registry = MetricDefinitionRegistry()
    registry.register(_derived("ROAS", ("AD_SALES", "AD_SPEND"), "AD_SALES / AD_SPEND"))
    assert registry.get("ROAS").metric == "ROAS"
    assert registry.get("ROAS", "1.0").version == "1.0"


def test_duplicate_metric_rejected():
    registry = MetricDefinitionRegistry()
    registry.register(_derived("ROAS", ("AD_SALES", "AD_SPEND"), "AD_SALES / AD_SPEND"))
    with pytest.raises(DuplicateMetricDefinitionError):
        registry.register(_derived("ROAS", ("A", "B"), "A / B"))


def test_unknown_metric():
    registry = MetricDefinitionRegistry()
    with pytest.raises(UnknownMetricError):
        registry.get("NOPE")


def test_unknown_version():
    registry = MetricDefinitionRegistry()
    registry.register(_derived("ROAS", ("AD_SALES", "AD_SPEND"), "AD_SALES / AD_SPEND"))
    with pytest.raises(UnknownMetricVersionError):
        registry.get("ROAS", "99.0")


def test_derived_requires_formula_and_dependencies():
    registry = MetricDefinitionRegistry()
    with pytest.raises(MetricDefinitionError):
        registry.register(MetricDefinition(
            metric="ROAS", metric_class=METRIC_CLASS_DERIVED, version="1.0",
        ))
    with pytest.raises(MetricDefinitionError):
        registry.register(MetricDefinition(
            metric="ROAS", metric_class=METRIC_CLASS_DERIVED, version="1.0",
            formula="A / B",
        ))


def test_source_metric_must_not_have_formula():
    registry = MetricDefinitionRegistry()
    with pytest.raises(MetricDefinitionError):
        registry.register(MetricDefinition(
            metric="GMV", metric_class=METRIC_CLASS_SOURCE, version="1.0",
            formula="A / B",
        ))


def test_unknown_zero_policy_rejected():
    registry = MetricDefinitionRegistry()
    with pytest.raises(MetricDefinitionError):
        registry.register(MetricDefinition(
            metric="ROAS", metric_class=METRIC_CLASS_DERIVED, version="1.0",
            dependencies=("A", "B"), formula="A / B", zero_policy="BOGUS",
        ))


def test_negative_precision_rejected():
    registry = MetricDefinitionRegistry()
    with pytest.raises(MetricDefinitionError):
        registry.register(MetricDefinition(
            metric="ROAS", metric_class=METRIC_CLASS_DERIVED, version="1.0",
            dependencies=("A", "B"), formula="A / B", precision=-1,
        ))


def test_formula_undeclared_identifier_rejected():
    registry = MetricDefinitionRegistry()
    with pytest.raises(MetricDefinitionError):
        registry.register(_derived("ROAS", ("AD_SALES", "AD_SPEND"), "AD_SALES / OTHER"))
