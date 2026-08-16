"""Phase 15.3 Tenant Platform tests."""

from types import SimpleNamespace

import pytest

from app.platform.production.errors import (
    QuotaExceededError,
    TenantIsolationViolationError,
)
from app.platform.production.tenant import (
    QuotaManager,
    Tenant,
    TenantIsolation,
    TenantQuota,
)


def test_tenant_model_and_statuses():
    tenant = Tenant(tenant_id="company_A", name="Acme", plan="enterprise")
    assert tenant.status == "ACTIVE"
    with pytest.raises(ValueError):
        Tenant(tenant_id="x", status="BOGUS")


def test_isolation_fails_closed():
    isolation = TenantIsolation()
    with pytest.raises(TenantIsolationViolationError):
        isolation.ensure_owner("company_A", "company_B")
    resource = SimpleNamespace(tenant_id="company_A")
    isolation.ensure_resource("company_A", resource)


def test_isolation_rejects_cross_tenant_in_result_set():
    isolation = TenantIsolation()
    items = [SimpleNamespace(tenant_id="company_A"),
             SimpleNamespace(tenant_id="company_B")]
    with pytest.raises(TenantIsolationViolationError):
        isolation.filter("company_A", items)


def test_quota_enforcement():
    manager = QuotaManager([TenantQuota(tenant_id="company_A", max_agents=2)])
    manager.consume("company_A", "agents", 1)
    manager.consume("company_A", "agents", 1)
    with pytest.raises(QuotaExceededError):
        manager.consume("company_A", "agents", 1)


def test_quota_unlimited_and_missing():
    manager = QuotaManager([TenantQuota(tenant_id="company_A", max_agents=None)])
    manager.consume("company_A", "agents", 100)  # unlimited
    manager.consume("company_B", "agents", 100)  # no quota -> allowed
