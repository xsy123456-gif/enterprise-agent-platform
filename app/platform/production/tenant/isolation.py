"""Tenant isolation (Phase 15.3).

Tenant isolation is the first priority.  ``TenantIsolation`` fails closed on any
cross-tenant resource access; resources never carry a tenant the caller can
override.
"""

from app.platform.production.errors import TenantIsolationViolationError


class TenantIsolation:

    def ensure_owner(self, tenant_id, resource_tenant_id):
        if resource_tenant_id != tenant_id:
            raise TenantIsolationViolationError(
                f"cross-tenant access denied: expected {tenant_id!r}, "
                f"resource belongs to {resource_tenant_id!r}"
            )

    def ensure_resource(self, tenant_id, resource):
        self.ensure_owner(tenant_id, getattr(resource, "tenant_id", None))

    def filter(self, tenant_id, items):
        owned = []
        for item in items:
            item_tenant = getattr(item, "tenant_id", None)
            if item_tenant is not None and item_tenant != tenant_id:
                raise TenantIsolationViolationError(
                    f"cross-tenant resource in result set for {tenant_id!r}"
                )
            owned.append(item)
        return owned


__all__ = ["TenantIsolation"]
