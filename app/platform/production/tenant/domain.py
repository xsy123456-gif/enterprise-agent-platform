"""Tenant model (Phase 15.3)."""

from dataclasses import dataclass, field

from app.commerce.domain.base import utc_now

TENANT_ACTIVE = "ACTIVE"
TENANT_SUSPENDED = "SUSPENDED"
TENANT_DISABLED = "DISABLED"
TENANT_STATUSES = frozenset({TENANT_ACTIVE, TENANT_SUSPENDED, TENANT_DISABLED})


@dataclass(frozen=True)
class Tenant:
    tenant_id: str
    name: str = ""
    status: str = TENANT_ACTIVE
    plan: str = ""
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if self.status not in TENANT_STATUSES:
            raise ValueError(f"unknown tenant status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "status": self.status,
            "plan": self.plan,
            "created_at": self.created_at,
        }


__all__ = [
    "Tenant",
    "TENANT_STATUSES",
    "TENANT_ACTIVE",
    "TENANT_SUSPENDED",
    "TENANT_DISABLED",
]
