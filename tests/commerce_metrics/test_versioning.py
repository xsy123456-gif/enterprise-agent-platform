"""Multi-version definition coexistence and replay determinism tests."""

from app.commerce.diagnostics import MetricEngine, MetricRequirementResolver
from app.commerce.diagnostics.registry.metric_registry import MetricDefinitionRegistry
from app.commerce.domain.metrics import (
    METRIC_CLASS_DERIVED,
    METRIC_CLASS_SOURCE,
    MetricDefinition,
)


def _source(name):
    return MetricDefinition(metric=name, metric_class=METRIC_CLASS_SOURCE, version="1.0")


def _registry_with_two_roas_versions():
    registry = MetricDefinitionRegistry()
    registry.register(_source("AD_SALES"))
    registry.register(_source("AD_SPEND"))
    registry.register(MetricDefinition(
        metric="ROAS", metric_class=METRIC_CLASS_DERIVED, version="1.0",
        dependencies=("AD_SALES", "AD_SPEND"), formula="AD_SALES / AD_SPEND",
        precision=4,
    ))
    registry.register(MetricDefinition(
        metric="ROAS", metric_class=METRIC_CLASS_DERIVED, version="2.0",
        dependencies=("AD_SALES", "AD_SPEND"), formula="AD_SALES / AD_SPEND",
        precision=6,
    ))
    registry.register(MetricDefinition(
        metric="ROAS_TIMES_10", metric_class=METRIC_CLASS_DERIVED, version="1.0",
        dependencies=("ROAS",), formula="ROAS * 10",
        dependency_versions={"ROAS": "1.0"},
    ))
    return registry


def test_multiple_versions_coexist():
    registry = _registry_with_two_roas_versions()
    assert set(registry.versions("ROAS")) == {"1.0", "2.0"}
    assert registry.active_version("ROAS") == "1.0"


def test_compute_explicit_historical_version():
    registry = _registry_with_two_roas_versions()
    engine = MetricEngine(registry)
    values = {"AD_SALES": 100.0, "AD_SPEND": 30.0}
    v1 = engine.compute("ROAS", values, version="1.0")
    v2 = engine.compute("ROAS", values, version="2.0")
    assert v1.value == 3.3333  # precision 4
    assert v2.value == 3.333333  # precision 6
    assert v1.version == "1.0"
    assert v2.version == "2.0"


def test_replay_does_not_drift_to_latest():
    registry = _registry_with_two_roas_versions()
    engine = MetricEngine(registry)
    values = {"AD_SALES": 100.0, "AD_SPEND": 30.0}

    before = engine.compute("ROAS_TIMES_10", values)
    assert before.value == 33.333  # uses ROAS@1.0 (3.3333 * 10)

    # Promote ROAS@2.0 to active; the pinned dependency must not drift.
    registry.activate("ROAS", "2.0")
    after = engine.compute("ROAS_TIMES_10", values)
    assert after.value == 33.333  # still ROAS@1.0

    # Direct (active) resolution now returns v2.0.
    assert engine.compute("ROAS", values).version == "2.0"


def test_resolver_version_determinism():
    registry = _registry_with_two_roas_versions()
    resolver = MetricRequirementResolver(registry)
    assert resolver.resolve("ROAS_TIMES_10") == ["AD_SALES", "AD_SPEND"]
    registry.activate("ROAS", "2.0")
    # Pinned dependency keeps resolution stable regardless of active version.
    assert resolver.resolve("ROAS_TIMES_10") == ["AD_SALES", "AD_SPEND"]


def test_unpinned_derived_dependency_rejected():
    registry = MetricDefinitionRegistry()
    registry.register(_source("X"))
    registry.register(MetricDefinition(
        metric="A", metric_class=METRIC_CLASS_DERIVED, version="1.0",
        dependencies=("X",), formula="X",
    ))
    registry.register(MetricDefinition(
        metric="B", metric_class=METRIC_CLASS_DERIVED, version="1.0",
        dependencies=("A",), formula="A * 2",
    ))
    engine = MetricEngine(registry)
    from app.commerce.diagnostics.errors import UnpinnedDependencyError
    import pytest
    with pytest.raises(UnpinnedDependencyError):
        engine.compute("B", {"X": 1.0})
