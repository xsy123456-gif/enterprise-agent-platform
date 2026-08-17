"""Entitlement + usage metering (Phase 16.6)."""

from app.platform.business.commercial.subscription import (
    PLAN_ENTERPRISE,
    PLAN_FREE,
    PLAN_PRO,
    SUBSCRIPTION_ACTIVE,
)
from app.platform.business.errors import EntitlementError

FEATURE_MULTI_AGENT = "multi_agent"
FEATURE_WORKFLOW = "workflow"
FEATURE_ERP_CONNECTOR = "erp_connector"
FEATURE_ADVANCED_KNOWLEDGE = "advanced_knowledge"

PLAN_FEATURES = {
    PLAN_FREE: {
        FEATURE_MULTI_AGENT: False,
        FEATURE_WORKFLOW: False,
        FEATURE_ERP_CONNECTOR: False,
        FEATURE_ADVANCED_KNOWLEDGE: False,
    },
    PLAN_PRO: {
        FEATURE_MULTI_AGENT: True,
        FEATURE_WORKFLOW: True,
        FEATURE_ERP_CONNECTOR: False,
        FEATURE_ADVANCED_KNOWLEDGE: False,
    },
    PLAN_ENTERPRISE: {
        FEATURE_MULTI_AGENT: True,
        FEATURE_WORKFLOW: True,
        FEATURE_ERP_CONNECTOR: True,
        FEATURE_ADVANCED_KNOWLEDGE: True,
    },
}

METRIC_AGENT_EXECUTIONS = "agent_executions"
METRIC_TOKENS = "tokens"
METRIC_WORKFLOWS = "workflows"
METRIC_CONNECTOR_CALLS = "connector_calls"


class EntitlementManager:

    def __init__(self, subscriptions=None):
        self._subscriptions = {s.tenant_id: s for s in (subscriptions or [])}

    def entitled(self, tenant_id, feature) -> bool:
        subscription = self._subscriptions.get(tenant_id)
        if subscription is None:
            return False
        if subscription.status != SUBSCRIPTION_ACTIVE:
            return False
        return PLAN_FEATURES.get(subscription.plan, {}).get(feature, False)

    def require(self, tenant_id, feature):
        if not self.entitled(tenant_id, feature):
            raise EntitlementError(
                f"tenant {tenant_id!r} lacks entitlement {feature!r}"
            )

    def subscription(self, tenant_id):
        return self._subscriptions.get(tenant_id)


class UsageMetering:

    def __init__(self):
        self._usage = {}

    def record(self, tenant_id, metric, amount=1):
        self._usage[(tenant_id, metric)] = self._usage.get((tenant_id, metric), 0) + amount

    def usage(self, tenant_id, metric):
        return self._usage.get((tenant_id, metric), 0)

    def check_limit(self, tenant_id, metric, limit):
        if limit is None:
            return
        if self.usage(tenant_id, metric) >= limit:
            raise EntitlementError(
                f"tenant {tenant_id!r} exceeds {metric} limit ({limit})"
            )


__all__ = [
    "EntitlementManager",
    "UsageMetering",
    "PLAN_FEATURES",
    "FEATURE_MULTI_AGENT",
    "FEATURE_WORKFLOW",
    "FEATURE_ERP_CONNECTOR",
    "FEATURE_ADVANCED_KNOWLEDGE",
    "METRIC_AGENT_EXECUTIONS",
    "METRIC_TOKENS",
    "METRIC_WORKFLOWS",
    "METRIC_CONNECTOR_CALLS",
]
