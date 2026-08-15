"""Impact contract.

``impact_type`` is the *business impact code* (e.g. REVENUE_LOSS,
WASTED_AD_SPEND, INVENTORY_CAPITAL_EXPOSURE).  ``classification`` is how the
impact is known — OBSERVED / ESTIMATED / PROJECTED — and an estimated revenue
loss must never be reported as observed.  Every impact carries its formula
id/version for replay.
"""

from dataclasses import dataclass

from app.commerce.contracts.errors import CommerceValidationError
from app.commerce.contracts.subject import SubjectRef

IMPACT_CLASSIFICATION_OBSERVED = "OBSERVED"
IMPACT_CLASSIFICATION_ESTIMATED = "ESTIMATED"
IMPACT_CLASSIFICATION_PROJECTED = "PROJECTED"
IMPACT_CLASSIFICATIONS = frozenset({
    IMPACT_CLASSIFICATION_OBSERVED,
    IMPACT_CLASSIFICATION_ESTIMATED,
    IMPACT_CLASSIFICATION_PROJECTED,
})

# Backwards-compatible aliases (classification values).
IMPACT_OBSERVED = IMPACT_CLASSIFICATION_OBSERVED
IMPACT_ESTIMATED = IMPACT_CLASSIFICATION_ESTIMATED
IMPACT_PROJECTED = IMPACT_CLASSIFICATION_PROJECTED


@dataclass(frozen=True)
class Impact:
    impact_id: str
    impact_type: str          # business impact code, e.g. REVENUE_LOSS
    classification: str       # OBSERVED / ESTIMATED / PROJECTED
    value: float
    subject: SubjectRef | None = None
    unit: str = ""
    formula_id: str = ""
    formula_version: str = ""
    confidence: float | None = None

    def __post_init__(self):
        if not self.impact_type:
            raise CommerceValidationError("impact_type (business impact code) is required")
        if self.classification not in IMPACT_CLASSIFICATIONS:
            raise CommerceValidationError(
                f"unknown impact classification: {self.classification}"
            )

    def to_dict(self) -> dict:
        return {
            "impact_id": self.impact_id,
            "impact_type": self.impact_type,
            "classification": self.classification,
            "value": self.value,
            "subject": self.subject.to_dict() if self.subject else None,
            "unit": self.unit,
            "formula_id": self.formula_id,
            "formula_version": self.formula_version,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Impact":
        return cls(
            impact_id=data["impact_id"],
            impact_type=data["impact_type"],
            classification=data["classification"],
            value=data["value"],
            subject=SubjectRef.from_dict(data["subject"]) if data.get("subject") else None,
            unit=data.get("unit", ""),
            formula_id=data.get("formula_id", ""),
            formula_version=data.get("formula_version", ""),
            confidence=data.get("confidence"),
        )


__all__ = [
    "Impact",
    "IMPACT_CLASSIFICATIONS",
    "IMPACT_CLASSIFICATION_OBSERVED",
    "IMPACT_CLASSIFICATION_ESTIMATED",
    "IMPACT_CLASSIFICATION_PROJECTED",
    "IMPACT_OBSERVED",
    "IMPACT_ESTIMATED",
    "IMPACT_PROJECTED",
]
