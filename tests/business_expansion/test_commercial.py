"""Phase 16.6 Commercial Layer tests."""

import pytest

from app.platform.business.commercial import (
    EntitlementManager,
    TenantSubscription,
    UsageMetering,
)
from app.platform.business.errors import EntitlementError


def _manager():
    return EntitlementManager([
        TenantSubscription(tenant_id="free_co", plan="FREE"),
        TenantSubscription(tenant_id="pro_co", plan="PRO"),
        TenantSubscription(tenant_id="ent_co", plan="ENTERPRISE"),
    ])


def test_enterprise_has_erp_connector_free_does_not():
    manager = _manager()
    assert manager.entitled("ent_co", "erp_connector") is True
    assert manager.entitled("pro_co", "erp_connector") is False
    assert manager.entitled("free_co", "workflow") is False


def test_require_raises_without_entitlement():
    manager = _manager()
    manager.require("ent_co", "advanced_knowledge")
    with pytest.raises(EntitlementError):
        manager.require("free_co", "workflow")


def test_unknown_tenant_fails_closed():
    manager = _manager()
    assert manager.entitled("ghost", "workflow") is False


def test_suspended_subscription_denied():
    manager = EntitlementManager([
        TenantSubscription(tenant_id="suspended_co", plan="ENTERPRISE",
                           status="SUSPENDED")])
    assert manager.entitled("suspended_co", "workflow") is False


def test_usage_metering_and_limit():
    metering = UsageMetering()
    metering.record("ent_co", "agent_executions", 5)
    metering.record("ent_co", "agent_executions", 5)
    assert metering.usage("ent_co", "agent_executions") == 10
    with pytest.raises(EntitlementError):
        metering.check_limit("ent_co", "agent_executions", 10)
