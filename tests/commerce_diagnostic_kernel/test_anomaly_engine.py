"""AnomalyEngine tests: multi-factor decision model, sample sufficiency, statuses."""

import pytest

from app.commerce.contracts.signal import (
    SIGNAL_ABNORMAL,
    SIGNAL_CRITICAL,
    SIGNAL_INSUFFICIENT_DATA,
    SIGNAL_NORMAL,
    SIGNAL_NOT_APPLICABLE,
    SIGNAL_UNKNOWN,
    SIGNAL_WARNING,
)
from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics import AnomalyEngine, DiagnosticPolicy

SUBJECT = SubjectRef("STORE", "store_amazon_001")


@pytest.fixture
def engine():
    return AnomalyEngine()


@pytest.fixture
def policy():
    return DiagnosticPolicy(policy_id="commerce.anomaly.v1", version="1.0",
                            min_baseline_volume=1.0, min_sample_size=3)


def _detect(engine, policy, current, baseline, series=None):
    return engine.detect(
        subject=SUBJECT, signal_code="GMV", domain="sales",
        current_value=current, baseline_value=baseline,
        baseline_series=series or [baseline] * 7, policy=policy,
    )


def test_normal(engine, policy):
    assert _detect(engine, policy, 102.0, 100.0).status == SIGNAL_NORMAL


def test_warning(engine, policy):
    assert _detect(engine, policy, 112.0, 100.0).status == SIGNAL_WARNING


def test_abnormal(engine, policy):
    assert _detect(engine, policy, 125.0, 100.0).status == SIGNAL_ABNORMAL


def test_critical(engine, policy):
    assert _detect(engine, policy, 150.0, 100.0).status == SIGNAL_CRITICAL


def test_direction_down(engine, policy):
    result = _detect(engine, policy, 60.0, 100.0)
    assert result.status == SIGNAL_CRITICAL
    assert result.direction == "DOWN"


def test_insufficient_low_baseline_volume(engine, policy):
    result = _detect(engine, policy, 100.0, 0.5)
    assert result.status == SIGNAL_INSUFFICIENT_DATA


def test_insufficient_small_sample(engine, policy):
    result = engine.detect(
        subject=SUBJECT, signal_code="GMV", domain="sales",
        current_value=100.0, baseline_value=90.0,
        baseline_series=[90.0, 91.0], policy=policy,
    )
    assert result.status == SIGNAL_INSUFFICIENT_DATA


def test_unknown_no_current(engine, policy):
    result = engine.detect(
        subject=SUBJECT, signal_code="GMV", domain="sales",
        current_value=None, baseline_value=100.0, baseline_series=[100.0] * 7,
        policy=policy,
    )
    assert result.status == SIGNAL_UNKNOWN


def test_not_applicable_subject_type(engine):
    policy = DiagnosticPolicy(
        policy_id="p", version="1.0", applicable_subject_types=("PRODUCT",)
    )
    result = engine.detect(
        subject=SUBJECT, signal_code="GMV", domain="sales",
        current_value=100.0, baseline_value=90.0, baseline_series=[90.0] * 7,
        policy=policy,
    )
    assert result.status == SIGNAL_NOT_APPLICABLE


def test_zscore_drives_severity(engine, policy):
    # Tiny but non-zero historical variance makes a small current shift a huge
    # z-score anomaly (relative change alone would be NORMAL).
    series = [100.0, 100.0, 100.0, 100.1, 99.9, 100.0, 100.0]
    result = engine.detect(
        subject=SUBJECT, signal_code="GMV", domain="sales",
        current_value=103.0, baseline_value=100.0, baseline_series=series,
        policy=policy,
    )
    assert result.status in (SIGNAL_ABNORMAL, SIGNAL_CRITICAL)


def test_algorithm_version_recorded(engine, policy):
    result = _detect(engine, policy, 150.0, 100.0)
    assert result.algorithm_version == "relative_change_zscore_v1"
    assert result.policy_version == "1.0"


def test_absolute_materiality_floor(engine):
    # Without a materiality floor, a 100% relative change flags CRITICAL.
    no_floor = DiagnosticPolicy(policy_id="p", version="1.0",
                                min_baseline_volume=0.0, min_sample_size=0)
    result = _detect(engine, no_floor, 2.0, 1.0, series=[1.0] * 7)
    assert result.status == SIGNAL_CRITICAL

    # With a materiality floor of 50, the same absolute change (+1.0) is immaterial.
    floor = DiagnosticPolicy(policy_id="p", version="1.0",
                             min_baseline_volume=0.0, min_sample_size=0,
                             minimum_absolute_change=50.0)
    result = _detect(engine, floor, 2.0, 1.0, series=[1.0] * 7)
    assert result.status == SIGNAL_NORMAL
