"""MetricRequirementResolver tests: leaf resolution + cycle detection."""

import pytest

from app.commerce.diagnostics.errors import (
    CyclicDependencyError,
    UnknownMetricError,
    UnpinnedDependencyError,
)
from app.commerce.diagnostics.registry.metric_registry import MetricDefinitionRegistry
from app.commerce.diagnostics.registry.resolver import MetricRequirementResolver
from app.commerce.domain.metrics import (
    METRIC_CLASS_DERIVED,
    METRIC_CLASS_SOURCE,
    MetricDefinition,
)


def _derived(metric, deps, formula="A", dependency_versions=None):
    return MetricDefinition(
        metric=metric, metric_class=METRIC_CLASS_DERIVED, version="1.0",
        dependencies=tuple(deps), formula=formula,
        dependency_versions=dependency_versions or {},
    )


def _source(metric):
    return MetricDefinition(metric=metric, metric_class=METRIC_CLASS_SOURCE, version="1.0")


def _registry_with_roas():
    registry = MetricDefinitionRegistry()
    registry.register(_source("AD_SALES"))
    registry.register(_source("AD_SPEND"))
    registry.register(_derived("ROAS", ("AD_SALES", "AD_SPEND"), "AD_SALES / AD_SPEND"))
    return registry


def test_roas_resolves_to_leaf_dependencies():
    registry = _registry_with_roas()
    resolver = MetricRequirementResolver(registry)
    assert resolver.resolve("ROAS") == ["AD_SALES", "AD_SPEND"]


def test_source_metric_resolves_to_itself():
    registry = _registry_with_roas()
    resolver = MetricRequirementResolver(registry)
    assert resolver.resolve("AD_SALES") == ["AD_SALES"]


def test_nested_derived_resolves_to_leaves():
    registry = MetricDefinitionRegistry()
    registry.register(_source("X"))
    registry.register(_source("Y"))
    registry.register(_derived("A", ("X", "Y"), "X / Y"))
    registry.register(_derived("B", ("A",), "A * 2", dependency_versions={"A": "1.0"}))
    resolver = MetricRequirementResolver(registry)
    assert resolver.resolve("B") == ["X", "Y"]


def test_shared_dependencies_deduplicated():
    registry = MetricDefinitionRegistry()
    registry.register(_source("X"))
    registry.register(_source("Y"))
    registry.register(_derived("A", ("X",), "X"))
    registry.register(_derived("B", ("X", "Y"), "X / Y"))
    registry.register(_derived("C", ("A", "B"), "A / B",
                               dependency_versions={"A": "1.0", "B": "1.0"}))
    resolver = MetricRequirementResolver(registry)
    assert resolver.resolve("C") == ["X", "Y"]


def test_cycle_detected():
    registry = MetricDefinitionRegistry()
    registry.register(_derived("A", ("B",), "B", dependency_versions={"B": "1.0"}))
    registry.register(_derived("B", ("A",), "A", dependency_versions={"A": "1.0"}))
    resolver = MetricRequirementResolver(registry)
    with pytest.raises(CyclicDependencyError):
        resolver.resolve("A")


def test_self_cycle_detected():
    registry = MetricDefinitionRegistry()
    registry.register(_derived("A", ("A",), "A", dependency_versions={"A": "1.0"}))
    resolver = MetricRequirementResolver(registry)
    with pytest.raises(CyclicDependencyError):
        resolver.resolve("A")


def test_unpinned_derived_dependency_rejected():
    registry = MetricDefinitionRegistry()
    registry.register(_source("X"))
    registry.register(_derived("A", ("X",), "X"))
    registry.register(_derived("B", ("A",), "A * 2"))
    resolver = MetricRequirementResolver(registry)
    with pytest.raises(UnpinnedDependencyError):
        resolver.resolve("B")


def test_unknown_dependency_raises():
    registry = MetricDefinitionRegistry()
    registry.register(_derived("ROAS", ("AD_SALES", "AD_SPEND"), "AD_SALES / AD_SPEND"))
    resolver = MetricRequirementResolver(registry)
    with pytest.raises(UnknownMetricError):
        resolver.resolve("ROAS")
