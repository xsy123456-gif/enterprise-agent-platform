"""PriorityEngine — versioned weighted priority scoring.

Priority is NOT severity.  Severity is one of five weighted factors; the engine
computes the normalized weighted score and maps it to P0/P1/P2/P3 using the
policy's thresholds.  All weights and thresholds come from a versioned
``PriorityPolicy``.
"""

from app.commerce.contracts.diagnostic_result import (
    PRIORITY_P0,
    PRIORITY_P1,
    PRIORITY_P2,
    PRIORITY_P3,
    Priority,
)
from app.commerce.diagnostics.definitions.priority import PRIORITY_FACTORS

ALGORITHM_VERSION = "weighted_score_v1"


def _fmt(value):
    return f"{value:.3f}"


class PriorityEngine:
    ALGORITHM_VERSION = ALGORITHM_VERSION

    def compute(self, factors, policy):
        """Map ``PriorityFactors`` to a ``Priority`` using ``policy``."""
        weighted = sum(
            policy.weight_for(factor) * getattr(factors, factor)
            for factor in PRIORITY_FACTORS
        )
        total_weight = sum(policy.weight_for(factor) for factor in PRIORITY_FACTORS)
        score = weighted / total_weight if total_weight else 0.0
        if score >= policy.p0_threshold:
            level = PRIORITY_P0
        elif score >= policy.p1_threshold:
            level = PRIORITY_P1
        elif score >= policy.p2_threshold:
            level = PRIORITY_P2
        else:
            level = PRIORITY_P3
        return Priority(
            level=level,
            severity=_fmt(factors.severity),
            business_impact=_fmt(factors.business_impact),
            urgency=_fmt(factors.urgency),
            confidence=factors.confidence,
            actionability=_fmt(factors.actionability),
            policy_id=policy.policy_id,
            policy_version=policy.version,
            score=round(score, 4),
        )


__all__ = ["PriorityEngine", "ALGORITHM_VERSION"]
