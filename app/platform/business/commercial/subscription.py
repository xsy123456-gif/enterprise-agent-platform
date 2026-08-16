"""Tenant subscription (Phase 16.6)."""

from dataclasses import dataclass, field

from app.core.time import utc_now

PLAN_FREE = "FREE"
PLAN_PRO = "PRO"
PLAN_ENTERPRISE = "ENTERPRISE"
PLANS = frozenset({PLAN_FREE, PLAN_PRO, PLAN_ENTERPRISE})

SUBSCRIPTION_ACTIVE = "ACTIVE"
SUBSCRIPTION_SUSPENDED = "SUSPENDED"
SUBSCRIPTION_STATUSES = frozenset({SUBSCRIPTION_ACTIVE, SUBSCRIPTION_SUSPENDED})


@dataclass(frozen=True)
class TenantSubscription:
    tenant_id: str
    plan: str = PLAN_FREE
    limits: dict = field(default_factory=dict)
    status: str = SUBSCRIPTION_ACTIVE
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        object.__setattr__(self, "limits", dict(self.limits or {}))
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if self.plan not in PLANS:
            raise ValueError(f"unknown plan: {self.plan}")
        if self.status not in SUBSCRIPTION_STATUSES:
            raise ValueError(f"unknown subscription status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "plan": self.plan,
            "limits": dict(self.limits),
            "status": self.status,
            "created_at": self.created_at,
        }


__all__ = [
    "TenantSubscription",
    "PLANS",
    "PLAN_FREE",
    "PLAN_PRO",
    "PLAN_ENTERPRISE",
    "SUBSCRIPTION_STATUSES",
    "SUBSCRIPTION_ACTIVE",
    "SUBSCRIPTION_SUSPENDED",
]
