"""Tenant quota (Phase 15.3)."""

from dataclasses import dataclass

from app.platform.production.errors import QuotaExceededError


@dataclass(frozen=True)
class TenantQuota:
    tenant_id: str
    max_agents: int | None = None
    max_execution: int | None = None
    max_tokens: int | None = None
    max_storage: int | None = None

    def __post_init__(self):
        if not self.tenant_id:
            raise ValueError("tenant_id is required")


class QuotaManager:

    def __init__(self, quotas=None):
        self._quotas = {q.tenant_id: q for q in (quotas or [])}
        self._usage = {}

    def check(self, tenant_id, metric, requested=1):
        quota = self._quotas.get(tenant_id)
        if quota is None:
            return
        limit = getattr(quota, f"max_{metric}", None)
        if limit is None:
            return
        current = self._usage.get((tenant_id, metric), 0)
        if current + requested > limit:
            raise QuotaExceededError(
                f"tenant {tenant_id!r} exceeds {metric} quota "
                f"({current + requested} > {limit})"
            )

    def consume(self, tenant_id, metric, amount=1):
        self.check(tenant_id, metric, amount)
        self._usage[(tenant_id, metric)] = self._usage.get((tenant_id, metric), 0) + amount

    def usage(self, tenant_id, metric):
        return self._usage.get((tenant_id, metric), 0)


__all__ = ["TenantQuota", "QuotaManager"]
