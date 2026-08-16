"""Approval request model (Phase 16.2)."""

from dataclasses import dataclass, field

from app.commerce.domain.base import utc_now

APPROVAL_PENDING = "PENDING"
APPROVAL_APPROVED = "APPROVED"
APPROVAL_REJECTED = "REJECTED"
APPROVAL_EXPIRED = "EXPIRED"
APPROVAL_CANCELLED = "CANCELLED"
APPROVAL_STATUSES = frozenset({
    APPROVAL_PENDING, APPROVAL_APPROVED, APPROVAL_REJECTED, APPROVAL_EXPIRED,
    APPROVAL_CANCELLED,
})

RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"
RISK_CRITICAL = "CRITICAL"
RISK_LEVELS = frozenset({RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_CRITICAL})


@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: str
    action_id: str = ""
    tenant_id: str = ""
    requester: str = ""
    risk_level: str = RISK_LOW
    status: str = APPROVAL_PENDING
    created_at: str = field(default_factory=utc_now)
    approved_by: str = ""
    approved_at: str = ""

    def __post_init__(self):
        if not self.approval_id:
            raise ValueError("approval_id is required")
        if self.status not in APPROVAL_STATUSES:
            raise ValueError(f"unknown approval status: {self.status}")
        if self.risk_level not in RISK_LEVELS:
            raise ValueError(f"unknown risk level: {self.risk_level}")

    def to_dict(self) -> dict:
        return {
            "approval_id": self.approval_id,
            "action_id": self.action_id,
            "tenant_id": self.tenant_id,
            "requester": self.requester,
            "risk_level": self.risk_level,
            "status": self.status,
            "created_at": self.created_at,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
        }


__all__ = [
    "ApprovalRequest",
    "APPROVAL_STATUSES",
    "APPROVAL_PENDING",
    "APPROVAL_APPROVED",
    "APPROVAL_REJECTED",
    "APPROVAL_EXPIRED",
    "APPROVAL_CANCELLED",
    "RISK_LEVELS",
    "RISK_LOW",
    "RISK_MEDIUM",
    "RISK_HIGH",
    "RISK_CRITICAL",
]
