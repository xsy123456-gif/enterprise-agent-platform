"""Impact contract.

Impact strictly separates OBSERVED from ESTIMATED from PROJECTED: an estimated
revenue loss must never be reported as observed.  Every impact carries its
formula id/version for replay.
"""

from dataclasses import dataclass

from app.commerce.contracts.errors import CommerceValidationError
from app.commerce.contracts.subject import SubjectRef

IMPACT_OBSERVED = "OBSERVED"
IMPACT_ESTIMATED = "ESTIMATED"
IMPACT_PROJECTED = "PROJECTED"
IMPACT_TYPES = frozenset({IMPACT_OBSERVED, IMPACT_ESTIMATED, IMPACT_PROJECTED})


@dataclass(frozen=True)
class Impact:
    impact_id: str
    impact_type: str
    classification: str
    value: float
    subject: SubjectRef | None = None
    unit: str = ""
    formula_id: str = ""
    formula_version: str = ""
    confidence: float | None = None

    def __post_init__(self):
        if self.impact_type not in IMPACT_TYPES:
            raise CommerceValidationError(f"unknown impact type: {self.impact_type}")

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
    "IMPACT_TYPES",
    "IMPACT_OBSERVED",
    "IMPACT_ESTIMATED",
    "IMPACT_PROJECTED",
]
