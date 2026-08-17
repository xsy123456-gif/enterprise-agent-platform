"""Evidence contract.

Evidence is the atomic, auditable fact produced by the diagnostic chain.  It is
not a business conclusion: a ``Signal``, ``Cause`` or ``DiagnosticResult`` is
built on top of Evidence, and every Evidence carries provenance back to a
Canonical Record.
"""

from dataclasses import dataclass
from typing import Any

from app.commerce.contracts.errors import CommerceValidationError
from app.commerce.contracts.query import DataProvenance, TimeRange
from app.commerce.contracts.subject import SubjectRef

EVIDENCE_RAW = "RAW"
EVIDENCE_METRIC = "METRIC"
EVIDENCE_DERIVED = "DERIVED"
EVIDENCE_AI_DERIVED = "AI_DERIVED"
EVIDENCE_TYPES = frozenset({EVIDENCE_RAW, EVIDENCE_METRIC, EVIDENCE_DERIVED, EVIDENCE_AI_DERIVED})

EVIDENCE_QUALITY_VALID = "VALID"
EVIDENCE_QUALITY_PARTIAL = "PARTIAL"
EVIDENCE_QUALITY_STALE = "STALE"
EVIDENCE_QUALITY_MISSING = "MISSING"
EVIDENCE_QUALITY_INVALID = "INVALID"
EVIDENCE_QUALITIES = frozenset({
    EVIDENCE_QUALITY_VALID,
    EVIDENCE_QUALITY_PARTIAL,
    EVIDENCE_QUALITY_STALE,
    EVIDENCE_QUALITY_MISSING,
    EVIDENCE_QUALITY_INVALID,
})


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    subject: SubjectRef
    evidence_type: str
    code: str
    value: Any = None
    unit: str = ""
    period: TimeRange | None = None
    provenance: DataProvenance | None = None
    definition_version: str = ""
    algorithm_version: str = ""
    quality: str = EVIDENCE_QUALITY_VALID
    confidence: float | None = None

    def __post_init__(self):
        if self.evidence_type not in EVIDENCE_TYPES:
            raise CommerceValidationError(f"unknown evidence type: {self.evidence_type}")
        if self.quality not in EVIDENCE_QUALITIES:
            raise CommerceValidationError(f"unknown evidence quality: {self.quality}")

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "subject": self.subject.to_dict(),
            "evidence_type": self.evidence_type,
            "code": self.code,
            "value": self.value,
            "unit": self.unit,
            "period": self.period.to_dict() if self.period else None,
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "definition_version": self.definition_version,
            "algorithm_version": self.algorithm_version,
            "quality": self.quality,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Evidence":
        return cls(
            evidence_id=data["evidence_id"],
            subject=SubjectRef.from_dict(data["subject"]),
            evidence_type=data["evidence_type"],
            code=data["code"],
            value=data.get("value"),
            unit=data.get("unit", ""),
            period=TimeRange.from_dict(data["period"]) if data.get("period") else None,
            provenance=DataProvenance.from_dict(data["provenance"]) if data.get("provenance") else None,
            definition_version=data.get("definition_version", ""),
            algorithm_version=data.get("algorithm_version", ""),
            quality=data.get("quality", EVIDENCE_QUALITY_VALID),
            confidence=data.get("confidence"),
        )


__all__ = [
    "Evidence",
    "EVIDENCE_TYPES",
    "EVIDENCE_RAW",
    "EVIDENCE_METRIC",
    "EVIDENCE_DERIVED",
    "EVIDENCE_AI_DERIVED",
    "EVIDENCE_QUALITIES",
    "EVIDENCE_QUALITY_VALID",
    "EVIDENCE_QUALITY_PARTIAL",
    "EVIDENCE_QUALITY_STALE",
    "EVIDENCE_QUALITY_MISSING",
    "EVIDENCE_QUALITY_INVALID",
]
