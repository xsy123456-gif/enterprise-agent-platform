"""ImpactEngine tests: impact_type (business code) vs classification
(OBSERVED/ESTIMATED/PROJECTED), safe evaluation."""

import pytest

from app.commerce.contracts.errors import CommerceValidationError
from app.commerce.contracts.impact import (
    IMPACT_CLASSIFICATION_ESTIMATED,
    IMPACT_CLASSIFICATION_OBSERVED,
    IMPACT_CLASSIFICATION_PROJECTED,
)
from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics import ImpactEngine, ImpactFormula

SUBJECT = SubjectRef("STORE", "store_amazon_001")


def _formula(classification, impact_type="REVENUE_LOSS", expression="GMV_LOSS * 1",
             deps=("GMV_LOSS",)):
    return ImpactFormula(
        formula_id="est_revenue_loss", version="1.0", impact_type=impact_type,
        classification=classification, unit="currency", expression=expression,
        dependencies=deps,
    )


def test_observed_impact():
    engine = ImpactEngine()
    impact = engine.compute(
        _formula(IMPACT_CLASSIFICATION_OBSERVED, impact_type="WASTED_AD_SPEND",
                 expression="OBSERVED_WASTE * 1", deps=("OBSERVED_WASTE",)),
        {"OBSERVED_WASTE": 500.0}, subject=SUBJECT,
    )
    assert impact.classification == IMPACT_CLASSIFICATION_OBSERVED
    assert impact.impact_type == "WASTED_AD_SPEND"
    assert impact.value == 500.0


def test_estimated_impact():
    engine = ImpactEngine()
    impact = engine.compute(
        _formula(IMPACT_CLASSIFICATION_ESTIMATED,
                 expression="GMV_BASELINE * DROP_RATE",
                 deps=("GMV_BASELINE", "DROP_RATE")),
        {"GMV_BASELINE": 100000.0, "DROP_RATE": 0.1}, subject=SUBJECT,
    )
    assert impact.classification == IMPACT_CLASSIFICATION_ESTIMATED
    assert impact.impact_type == "REVENUE_LOSS"
    assert impact.value == 10000.0


def test_projected_impact():
    engine = ImpactEngine()
    impact = engine.compute(
        _formula(IMPACT_CLASSIFICATION_PROJECTED, impact_type="STOCKOUT_LOSS",
                 expression="DAILY_REVENUE * STOCKOUT_DAYS",
                 deps=("DAILY_REVENUE", "STOCKOUT_DAYS")),
        {"DAILY_REVENUE": 1000.0, "STOCKOUT_DAYS": 7}, subject=SUBJECT,
    )
    assert impact.classification == IMPACT_CLASSIFICATION_PROJECTED
    assert impact.impact_type == "STOCKOUT_LOSS"
    assert impact.value == 7000.0


def test_estimated_is_not_observed():
    engine = ImpactEngine()
    estimated = engine.compute(
        _formula(IMPACT_CLASSIFICATION_ESTIMATED,
                 expression="GMV_BASELINE * DROP_RATE",
                 deps=("GMV_BASELINE", "DROP_RATE")),
        {"GMV_BASELINE": 100000.0, "DROP_RATE": 0.1},
    )
    observed = engine.compute(
        _formula(IMPACT_CLASSIFICATION_OBSERVED, impact_type="WASTED_AD_SPEND",
                 expression="OBSERVED_WASTE * 1", deps=("OBSERVED_WASTE",)),
        {"OBSERVED_WASTE": 10000.0},
    )
    assert estimated.classification != observed.classification


def test_invalid_classification_rejected():
    with pytest.raises(CommerceValidationError):
        ImpactFormula(
            formula_id="f", version="1.0", impact_type="REVENUE_LOSS",
            classification="GUESSED", expression="A * 1", dependencies=("A",),
        )


def test_missing_impact_type_rejected():
    with pytest.raises(CommerceValidationError):
        ImpactFormula(
            formula_id="f", version="1.0", impact_type="",
            classification="ESTIMATED", expression="A * 1", dependencies=("A",),
        )


def test_no_arbitrary_code():
    engine = ImpactEngine()
    formula = ImpactFormula(
        formula_id="f", version="1.0", impact_type="REVENUE_LOSS",
        classification="ESTIMATED", expression="__import__('os')", dependencies=(),
    )
    from app.commerce.diagnostics.errors import MetricEvaluationError
    with pytest.raises(MetricEvaluationError):
        engine.compute(formula, {})


def test_formula_version_recorded():
    engine = ImpactEngine()
    impact = engine.compute(
        _formula(IMPACT_CLASSIFICATION_ESTIMATED, expression="X * 2", deps=("X",)),
        {"X": 5.0},
    )
    assert impact.formula_id == "est_revenue_loss"
    assert impact.formula_version == "1.0"
