"""ComparisonEngine tests: current/baseline/absolute/relative only."""

from app.commerce.diagnostics import ComparisonEngine, ComparisonResult


def test_basic_comparison():
    result = ComparisonEngine().compare(200.0, 100.0)
    assert result.current_value == 200.0
    assert result.baseline_value == 100.0
    assert result.absolute_change == 100.0
    assert result.relative_change == 1.0


def test_negative_change():
    result = ComparisonEngine().compare(50.0, 100.0)
    assert result.absolute_change == -50.0
    assert result.relative_change == -0.5


def test_zero_baseline_relative_none():
    result = ComparisonEngine().compare(100.0, 0.0)
    assert result.absolute_change == 100.0
    assert result.relative_change is None


def test_none_inputs():
    result = ComparisonEngine().compare(None, 100.0)
    assert result.absolute_change is None
    assert result.relative_change is None


def test_roundtrip():
    result = ComparisonEngine().compare(200.0, 100.0)
    assert ComparisonResult.from_dict(result.to_dict()) == result


def test_no_anomaly_classification():
    # ComparisonEngine only produces the four numeric fields; it must not add
    # an anomaly/status classification.
    result = ComparisonEngine().compare(1.0, 2.0)
    assert not hasattr(result, "status")
    assert not hasattr(result, "anomaly")
