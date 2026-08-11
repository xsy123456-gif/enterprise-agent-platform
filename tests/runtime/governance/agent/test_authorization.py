import pytest

from app.runtime.governance.agent import (
    AgentAuthorizationContext,
    AgentAuthorizationEngine,
    AgentInvocationPolicy,
    AgentInvocationPolicyStore,
    AuthorizationStatus,
)
from tests.runtime.governance.agent.helpers import node, policy_store, principal, request


def test_allowed_agent_invocation():
    decision = AgentAuthorizationEngine(policy_store()).authorize(request(), principal())
    assert decision.status is AuthorizationStatus.ALLOW
    assert decision.policy_id


def test_missing_policy_is_default_deny():
    decision = AgentAuthorizationEngine().authorize(request(), principal())
    assert decision.status is AuthorizationStatus.DENY
    assert decision.policy_id is None


def test_unauthenticated_user_identity_is_denied():
    decision = AgentAuthorizationEngine(policy_store()).authorize(
        request(), principal(False)
    )
    assert decision.status is AuthorizationStatus.DENY


def test_user_without_effective_capability_scope_is_denied():
    context = AgentAuthorizationContext("user-1", "tenant-1", True, frozenset())
    decision = AgentAuthorizationEngine(policy_store()).authorize(request(), context)
    assert decision.status is AuthorizationStatus.DENY
    assert "user capability scope" in decision.reason


def test_disallowed_capability_is_denied():
    store = policy_store(allowed_capabilities=frozenset({"other.capability"}))
    decision = AgentAuthorizationEngine(store).authorize(request(), principal())
    assert decision.status is AuthorizationStatus.DENY


def test_policy_can_require_approval():
    store = policy_store(approval_required=True, risk_level="high")
    decision = AgentAuthorizationEngine(store).authorize(request(), principal())
    assert decision.status is AuthorizationStatus.REQUIRE_APPROVAL


def test_policy_is_exact_for_source_and_target():
    other = node("risk")
    decision = AgentAuthorizationEngine(policy_store()).authorize(
        request(other), principal()
    )
    assert decision.status is AuthorizationStatus.DENY


def test_duplicate_source_target_policy_is_rejected():
    store = policy_store()
    with pytest.raises(ValueError, match="already exists"):
        store.register(next(iter(store._policies.values())))


@pytest.mark.parametrize("risk", ["low", "medium", "high", "critical"])
def test_supported_policy_risk_levels(risk):
    invocation_policy = AgentInvocationPolicy(
        "supervisor", "finance", frozenset({"finance.analysis"}),
        risk_level=risk,
    )
    assert invocation_policy.risk_level == risk


def test_invalid_policy_risk_is_rejected():
    with pytest.raises(ValueError, match="risk"):
        AgentInvocationPolicy(
            "supervisor", "finance", frozenset({"finance.analysis"}),
            risk_level="extreme",
        )
