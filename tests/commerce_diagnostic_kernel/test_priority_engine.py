"""PriorityEngine tests: Priority != Severity, weighted scoring, P-level mapping."""

import pytest

from app.commerce.diagnostics import (
    PriorityEngine,
    PriorityFactors,
    PriorityPolicy,
)


def _policy():
    return PriorityPolicy(policy_id="commerce.priority.v1", version="1.0")


def test_p0():
    engine = PriorityEngine()
    result = engine.compute(
        PriorityFactors(severity=1.0, business_impact=1.0, urgency=1.0,
                        confidence=1.0, actionability=1.0),
        _policy(),
    )
    assert result.level == "P0"


def test_p1():
    engine = PriorityEngine()
    result = engine.compute(
        PriorityFactors(severity=0.8, business_impact=0.7, urgency=0.7,
                        confidence=0.7, actionability=0.7),
        _policy(),
    )
    assert result.level == "P1"


def test_p3_low_factors():
    engine = PriorityEngine()
    result = engine.compute(
        PriorityFactors(severity=0.1, business_impact=0.1, urgency=0.1,
                        confidence=0.1, actionability=0.1),
        _policy(),
    )
    assert result.level == "P3"


def test_high_severity_alone_is_not_p0():
    # Priority != Severity: severity is only one weighted factor (weight 0.30).
    engine = PriorityEngine()
    result = engine.compute(
        PriorityFactors(severity=1.0, business_impact=0.0, urgency=0.0,
                        confidence=0.0, actionability=0.0),
        _policy(),
    )
    assert result.level != "P0"


def test_severity_recorded_as_factor_not_level():
    engine = PriorityEngine()
    result = engine.compute(
        PriorityFactors(severity=0.9, business_impact=0.5, urgency=0.5,
                        confidence=0.5, actionability=0.5),
        _policy(),
    )
    assert result.severity == "0.900"
    assert result.level in ("P1", "P2")


def test_policy_version_recorded():
    engine = PriorityEngine()
    result = engine.compute(
        PriorityFactors(0.8, 0.8, 0.8, 0.8, 0.8), _policy(),
    )
    assert result.policy_id == "commerce.priority.v1"
    assert result.policy_version == "1.0"
    assert result.score is not None


def test_weights_are_normalized():
    engine = PriorityEngine()
    policy = PriorityPolicy(
        policy_id="p", version="1.0",
        weights={"severity": 1.0, "business_impact": 0.0, "urgency": 0.0,
                 "confidence": 0.0, "actionability": 0.0},
    )
    result = engine.compute(
        PriorityFactors(severity=0.5, business_impact=1.0, urgency=1.0,
                        confidence=1.0, actionability=1.0),
        policy,
    )
    # only severity has weight, so score == severity == 0.5 -> P2.
    assert result.score == pytest.approx(0.5)
    assert result.level == "P2"
