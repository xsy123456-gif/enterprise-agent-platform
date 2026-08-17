"""ImpactFormula definition — declarative impact estimation.

``impact_type`` is the business impact code (e.g. REVENUE_LOSS);
``classification`` is strictly one of OBSERVED / ESTIMATED / PROJECTED.  The
formula is a declarative arithmetic expression over named inputs, evaluated by
the safe parser (never eval).
"""

from dataclasses import dataclass, field

from app.commerce.contracts.errors import CommerceValidationError
from app.commerce.contracts.impact import IMPACT_CLASSIFICATIONS


@dataclass(frozen=True)
class ImpactFormula:
    formula_id: str
    version: str
    impact_type: str          # business impact code, e.g. REVENUE_LOSS
    classification: str       # OBSERVED / ESTIMATED / PROJECTED
    unit: str = ""
    expression: str = ""
    dependencies: tuple[str, ...] = ()
    confidence: float | None = None

    def __post_init__(self):
        object.__setattr__(self, "dependencies", tuple(self.dependencies or ()))
        if not self.impact_type:
            raise CommerceValidationError("impact_type (business impact code) is required")
        if self.classification not in IMPACT_CLASSIFICATIONS:
            raise CommerceValidationError(
                f"unknown impact classification {self.classification!r}; expected "
                "OBSERVED, ESTIMATED or PROJECTED"
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
