"""Legacy governance PolicyDecisionEngine semantic parity tests.

Verifies the migrated authorization policies reproduce the legacy
PolicyDecisionEngine decisions exactly (100% parity).
"""

from pathlib import Path

import pytest

from app.governance.policy import (
    GovernancePolicy,
    InMemoryPolicyRepository,
    PolicyDecisionEngine,
    PolicyRule,
)
from app.permission import (
    Decision,
    PermissionConfig,
    PermissionEnvironment,
    PermissionRequest,
    PermissionResource,
    PermissionSubject,
    build_permission,
)

ROOT = Path(__file__).resolve().parents[2] / "data" / "permission" / "policies"


def _legacy_policy():
    return GovernancePolicy(
        policy_id="default_governance",
        name="legacy",
        rules=[
            PolicyRule("system", "create_agent", "*", "allow"),
            PolicyRule("developer", "submit_review", "*", "allow"),
            PolicyRule("admin", "approve_agent", "*", "allow"),
            PolicyRule("admin", "reject_agent", "*", "allow"),
            PolicyRule("admin", "activate_agent", "*", "allow"),
            PolicyRule("admin", "suspend_agent", "*", "allow"),
            PolicyRule("admin", "deprecate_agent", "*", "allow"),
        ],
    )


def _legacy_allows(role, action):
    engine = PolicyDecisionEngine(InMemoryPolicyRepository())
    engine.register(_legacy_policy())
    decision = engine.check({
        "user_id": "u", "role": role, "action": action,
        "agent_id": "a1", "version": "v1",
    })
    return decision.allowed


@pytest.fixture(scope="module")
def system():
    permission = build_permission(config=PermissionConfig(policy_root=str(ROOT)))
    permission.runtime.start()
    return permission


def _evaluate(system, role, action):
    subject = PermissionSubject(subject_id="u", tenant_id="company_A",
                               roles=frozenset({role}))
    resource = PermissionResource("agent", "a1", "company_A")
    request = PermissionRequest(
        "R", subject, resource, action, PermissionEnvironment()
    )
    return system.evaluate(request)


_ACTIONS = [
    "create_agent", "submit_review", "approve_agent", "reject_agent",
    "activate_agent", "suspend_agent", "deprecate_agent",
]
_ROLES = ["system", "developer", "admin", "unknown"]


@pytest.mark.parametrize("role", _ROLES)
@pytest.mark.parametrize("action", _ACTIONS)
def test_governance_policy_parity(system, role, action):
    expected = _legacy_allows(role, action)
    decision = _evaluate(system, role, action)
    assert (decision.decision is Decision.ALLOW) == expected
