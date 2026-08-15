"""ImpactFormula definition — declarative impact estimation.

Impact type is strictly one of OBSERVED / ESTIMATED / PROJECTED; a formula is a
declarative arithmetic expression over named inputs, evaluated by the safe
parser (never eval).  ``classification`` names the impact kind (e.g.
ESTIMATED_REVENUE_LOSS).
"""

from dataclasses import dataclass, field

from app.commerce.contracts.errors import CommerceValidationError
from app.commerce.contracts.impact import IMPACT_TYPES


@dataclass(frozen=True)
class ImpactFormula:
    formula_id: str
    version: str
    impact_type: str
    classification: str
    unit: str = ""
    expression: str = ""
    dependencies: tuple[str, ...] = ()
    confidence: float | None = None

    def __post_init__(self):
        object.__setattr__(self, "dependencies", tuple(self.dependencies or ()))
        if self.impact_type not in IMPACT_TYPES:
            raise CommerceValidationError(
                f"unknown impact_type {self.impact_type!r}; expected OBSERVED, "
                "ESTIMATED or PROJECTED"
            )

    def to_dict(self) -> dict:
        return {
            "formula_id": self.formula_id,
            "version": self.version,
            "impact_type": self.impact_type,
            "classification": self.classification,
            "unit": self.unit,
            "expression": self.expression,
            "dependencies": list(self.dependencies),
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ImpactFormula":
        return cls(
            formula_id=data["formula_id"],
            version=data["version"],
            impact_type=data["impact_type"],
            classification=data["classification"],
            unit=data.get("unit", ""),
            expression=data.get("expression", ""),
            dependencies=tuple(data.get("dependencies", ())),
            confidence=data.get("confidence"),
        )


__all__ = ["ImpactFormula"]
