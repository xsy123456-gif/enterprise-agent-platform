"""ImpactEngine tests: OBSERVED/ESTIMATED/PROJECTED distinction, safe evaluation."""

import pytest

from app.commerce.contracts.errors import CommerceValidationError
from app.commerce.contracts.impact import (
    IMPACT_ESTIMATED,
    IMPACT_OBSERVED,
    IMPACT_PROJECTED,
)
from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics import ImpactEngine, ImpactFormula

SUBJECT = SubjectRef("STORE", "store_amazon_001")


def _formula(impact_type, expression="GMV_LOSS * 1", deps=("GMV_LOSS",)):
    return ImpactFormula(
        formula_id="est_revenue_loss", version="1.0", impact_type=impact_type,
        classification="REVENUE_LOSS", unit="currency", expression=expression,
        dependencies=deps,
    )


def test_observed_impact():
    engine = ImpactEngine()
    impact = engine.compute(
        _formula(IMPACT_OBSERVED, "OBSERVED_WASTE * 1", ("OBSERVED_WASTE",)),
        {"OBSERVED_WASTE": 500.0}, subject=SUBJECT,
    )
    assert impact.impact_type == IMPACT_OBSERVED
    assert impact.value == 500.0


def test_estimated_impact():
    engine = ImpactEngine()
    impact = engine.compute(
        _formula(IMPACT_ESTIMATED, "GMV_BASELINE * DROP_RATE", ("GMV_BASELINE", "DROP_RATE")),
        {"GMV_BASELINE": 100000.0, "DROP_RATE": 0.1}, subject=SUBJECT,
    )
    assert impact.impact_type == IMPACT_ESTIMATED
    assert impact.value == 10000.0


def test_projected_impact():
    engine = ImpactEngine()
    impact = engine.compute(
        _formula(IMPACT_PROJECTED, "DAILY_REVENUE * STOCKOUT_DAYS",
                 ("DAILY_REVENUE", "STOCKOUT_DAYS")),
        {"DAILY_REVENUE": 1000.0, "STOCKOUT_DAYS": 7}, subject=SUBJECT,
    )
    assert impact.impact_type == IMPACT_PROJECTED
    assert impact.value == 7000.0


def test_estimated_is_not_observed():
    engine = ImpactEngine()
    estimated = engine.compute(
        _formula(IMPACT_ESTIMATED, "GMV_BASELINE * DROP_RATE", ("GMV_BASELINE", "DROP_RATE")),
        {"GMV_BASELINE": 100000.0, "DROP_RATE": 0.1},
    )
    observed = engine.compute(
        _formula(IMPACT_OBSERVED, "OBSERVED_WASTE * 1", ("OBSERVED_WASTE",)),
        {"OBSERVED_WASTE": 10000.0},
    )
    assert estimated.impact_type != observed.impact_type


def test_invalid_impact_type_rejected():
    with pytest.raises(CommerceValidationError):
        ImpactFormula(
            formula_id="f", version="1.0", impact_type="GUESSED",
            classification="X", expression="A * 1", dependencies=("A",),
        )


def test_no_arbitrary_code():
    engine = ImpactEngine()
    formula = ImpactFormula(
        formula_id="f", version="1.0", impact_type=IMPACT_ESTIMATED,
        classification="X", expression="__import__('os')", dependencies=(),
    )
    from app.commerce.diagnostics.errors import MetricEvaluationError
    with pytest.raises(MetricEvaluationError):
        engine.compute(formula, {})


def test_formula_version_recorded():
    engine = ImpactEngine()
    impact = engine.compute(
        _formula(IMPACT_ESTIMATED, "X * 2", ("X",)), {"X": 5.0},
    )
    assert impact.formula_id == "est_revenue_loss"
    assert impact.formula_version == "1.0"
