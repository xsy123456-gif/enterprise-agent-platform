"""Operations domain: OperationalIssue.

``OperationalIssue`` is the deterministic, tenant-scoped output of the
diagnostic chain (``DiagnosticResult -> IssueAssembler -> OperationalIssue``).
It is produced by the kernel, never freely created by an LLM.  It stores
references to supporting evidence / causes rather than inlining them, keeping
the evidence chain traceable.
"""

from dataclasses import dataclass, field
from typing import Any

from app.commerce.domain.base import utc_now


@dataclass(frozen=True)
class OperationalIssue:
    issue_id: str
    tenant_id: str
    store_id: str
    domain: str
    subject_type: str
    subject_id: str
    issue_type: str
    severity: str = ""
    priority: str = ""
    detected_at: str = field(default_factory=utc_now)
    evidence_refs: tuple[str, ...] = ()
    cause_refs: tuple[str, ...] = ()
    impacts: tuple[dict[str, Any], ...] = ()
    recommendation_codes: tuple[str, ...] = ()
    status: str = "open"
    source_diagnostic_id: str = ""
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs or ()))
        object.__setattr__(self, "cause_refs", tuple(self.cause_refs or ()))
        object.__setattr__(self, "impacts", tuple(dict(i) for i in (self.impacts or ())))
        object.__setattr__(self, "recommendation_codes", tuple(self.recommendation_codes or ()))

    def to_dict(self) -> dict:
        return {
            "issue_id": self.issue_id,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "domain": self.domain,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "priority": self.priority,
            "detected_at": self.detected_at,
            "evidence_refs": list(self.evidence_refs),
            "cause_refs": list(self.cause_refs),
            "impacts": [dict(i) for i in self.impacts],
            "recommendation_codes": list(self.recommendation_codes),
            "status": self.status,
            "source_diagnostic_id": self.source_diagnostic_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OperationalIssue":
        return cls(
            issue_id=data["issue_id"],
            tenant_id=data["tenant_id"],
            store_id=data["store_id"],
            domain=data["domain"],
            subject_type=data["subject_type"],
            subject_id=data["subject_id"],
            issue_type=data["issue_type"],
            severity=data.get("severity", ""),
            priority=data.get("priority", ""),
            detected_at=data.get("detected_at", utc_now()),
            evidence_refs=tuple(data.get("evidence_refs", ())),
            cause_refs=tuple(data.get("cause_refs", ())),
            impacts=tuple(dict(i) for i in data.get("impacts", ())),
            recommendation_codes=tuple(data.get("recommendation_codes", ())),
            status=data.get("status", "open"),
            source_diagnostic_id=data.get("source_diagnostic_id", ""),
            created_at=data.get("created_at", utc_now()),
        )


__all__ = ["OperationalIssue"]
