"""ImpactEngine — evaluates a versioned ImpactFormula.

Uses the same safe arithmetic parser as MetricEngine (no eval).  The impact
type (business impact code) and classification (OBSERVED / ESTIMATED /
PROJECTED) are carried through from the formula and validated by the ``Impact``
contract.
"""

import uuid

from app.commerce.contracts.impact import Impact
from app.commerce.diagnostics.kernel.formula import evaluate_expression

ALGORITHM_VERSION = "expression_eval_v1"

IMPACT_PRECISION = 4


class ImpactEngine:
    ALGORITHM_VERSION = ALGORITHM_VERSION

    def compute(self, formula, values, subject=None, impact_id=None):
        """Evaluate ``formula`` against ``values`` (name -> float).

        Returns an ``Impact`` carrying formula id/version for replay.
        """
        raw, _used = evaluate_expression(formula.expression, values)
        return Impact(
            impact_id=impact_id or uuid.uuid4().hex,
            impact_type=formula.impact_type,
            classification=formula.classification,
            value=round(raw, IMPACT_PRECISION),
            subject=subject,
            unit=formula.unit,
            formula_id=formula.formula_id,
            formula_version=formula.version,
            confidence=formula.confidence,
        )


__all__ = ["ImpactEngine", "ALGORITHM_VERSION"]
