"""TrendEngine tests: all six patterns, determinism, versioning."""

import pytest

from app.commerce.diagnostics import (
    TREND_GRADUAL,
    TREND_PERSISTENT,
    TREND_STABLE,
    TREND_SUDDEN,
    TREND_TRANSIENT,
    TREND_UNKNOWN,
    DiagnosticPolicy,
    TrendEngine,
)


@pytest.fixture
def engine():
    return TrendEngine()


@pytest.fixture
def policy():
    return DiagnosticPolicy(policy_id="commerce.trend.v1", version="1.0")


def test_stable(engine, policy):
    result = engine.detect_trend([100] * 10, policy)
    assert result.pattern == TREND_STABLE


def test_sudden(engine, policy):
    result = engine.detect_trend([100] * 9 + [200], policy)
    assert result.pattern == TREND_SUDDEN
    assert result.direction == "UP"


def test_persistent(engine, policy):
    result = engine.detect_trend([100] * 7 + [115] * 4, policy)
    assert result.pattern == TREND_PERSISTENT


def test_gradual(engine, policy):
    result = engine.detect_trend([100] * 10 + [106, 112], policy)
    assert result.pattern == TREND_GRADUAL


def test_transient(engine, policy):
    result = engine.detect_trend([100] * 4 + [140] + [100] * 4, policy)
    assert result.pattern == TREND_TRANSIENT


def test_unknown_insufficient_points(engine, policy):
    result = engine.detect_trend([100, 101], policy)
    assert result.pattern == TREND_UNKNOWN
    assert result.slope is None


def test_deterministic(engine, policy):
    series = [100] * 7 + [115] * 4
    assert engine.detect_trend(series, policy) == engine.detect_trend(series, policy)


def test_algorithm_and_policy_version_recorded(engine, policy):
    result = engine.detect_trend([100] * 10, policy)
    assert result.algorithm_version == "rolling_baseline_slope_v1"
    assert result.policy_version == "1.0"
    assert result.sample_size == 10
