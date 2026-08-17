"""Cause contract.

A Cause is the structured, evidence-backed explanation of a Signal.  It is
never a single free-form ``root_cause`` string: causal role (PRIMARY vs
CONTRIBUTING vs SECONDARY_EFFECT vs CORRELATED) and support level are first
class, and both supporting and contradicting evidence are recorded.
"""

from dataclasses import dataclass, field

from app.commerce.contracts.errors import CommerceValidationError
from app.commerce.contracts.subject import SubjectRef

ROLE_PRIMARY = "PRIMARY"
ROLE_CONTRIBUTING = "CONTRIBUTING"
ROLE_SECONDARY_EFFECT = "SECONDARY_EFFECT"
ROLE_CORRELATED = "CORRELATED"
CAUSAL_ROLES = frozenset({ROLE_PRIMARY, ROLE_CONTRIBUTING, ROLE_SECONDARY_EFFECT, ROLE_CORRELATED})

SUPPORT_CONFIRMED = "CONFIRMED"
SUPPORT_STRONGLY_SUPPORTED = "STRONGLY_SUPPORTED"
SUPPORT_SUPPORTED = "SUPPORTED"
SUPPORT_POSSIBLE = "POSSIBLE"
SUPPORT_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
SUPPORT_LEVELS = frozenset({
    SUPPORT_CONFIRMED,
    SUPPORT_STRONGLY_SUPPORTED,
    SUPPORT_SUPPORTED,
    SUPPORT_POSSIBLE,
    SUPPORT_INSUFFICIENT_EVIDENCE,
})


@dataclass(frozen=True)
class Cause:
    cause_id: str
    cause_code: str
    domain: str
    subject: SubjectRef
    causal_role: str = ROLE_CONTRIBUTING
    support_level: str = SUPPORT_POSSIBLE
    supporting_signal_ids: tuple[str, ...] = ()
    supporting_evidence_ids: tuple[str, ...] = ()
    contradicting_evidence_ids: tuple[str, ...] = ()
    rule_id: str = ""
    rule_version: str = ""
    score: float | None = None

    def __post_init__(self):
        object.__setattr__(self, "supporting_signal_ids", tuple(self.supporting_signal_ids or ()))
        object.__setattr__(self, "supporting_evidence_ids", tuple(self.supporting_evidence_ids or ()))
        object.__setattr__(self, "contradicting_evidence_ids", tuple(self.contradicting_evidence_ids or ()))
        if self.causal_role not in CAUSAL_ROLES:
            raise CommerceValidationError(f"unknown causal role: {self.causal_role}")
        if self.support_level not in SUPPORT_LEVELS:
            raise CommerceValidationError(f"unknown support level: {self.support_level}")

    def to_dict(self) -> dict:
        return {
            "cause_id": self.cause_id,
            "cause_code": self.cause_code,
            "domain": self.domain,
            "subject": self.subject.to_dict(),
            "causal_role": self.causal_role,
            "support_level": self.support_level,
            "supporting_signal_ids": list(self.supporting_signal_ids),
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "contradicting_evidence_ids": list(self.contradicting_evidence_ids),
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Cause":
        return cls(
            cause_id=data["cause_id"],
            cause_code=data["cause_code"],
            domain=data["domain"],
            subject=SubjectRef.from_dict(data["subject"]),
            causal_role=data.get("causal_role", ROLE_CONTRIBUTING),
            support_level=data.get("support_level", SUPPORT_POSSIBLE),
            supporting_signal_ids=tuple(data.get("supporting_signal_ids", ())),
            supporting_evidence_ids=tuple(data.get("supporting_evidence_ids", ())),
            contradicting_evidence_ids=tuple(data.get("contradicting_evidence_ids", ())),
            rule_id=data.get("rule_id", ""),
            rule_version=data.get("rule_version", ""),
            score=data.get("score"),
        )


__all__ = [
    "Cause",
    "CAUSAL_ROLES",
    "ROLE_PRIMARY",
    "ROLE_CONTRIBUTING",
    "ROLE_SECONDARY_EFFECT",
    "ROLE_CORRELATED",
    "SUPPORT_LEVELS",
    "SUPPORT_CONFIRMED",
    "SUPPORT_STRONGLY_SUPPORTED",
    "SUPPORT_SUPPORTED",
    "SUPPORT_POSSIBLE",
    "SUPPORT_INSUFFICIENT_EVIDENCE",
]
