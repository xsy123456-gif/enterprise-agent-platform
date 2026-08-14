"""Legacy PermissionManager semantic parity tests.

Verifies the migrated policies reproduce the old hard-coded RBAC decisions
exactly (100% parity), without changing the legacy runtime behavior.
"""

from pathlib import Path

import pytest

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

# Static legacy behavior matrix (PermissionManager semantics frozen as data).
_LEGACY = {
    "sales": {"crm_query", "financial_query", "market_query"},
    "manager": {"crm_query", "customer_update"},
    "admin": "*",
}

_TOOLS = ["crm_query", "financial_query", "market_query", "customer_update"]


@pytest.fixture(scope="module")
def system():
    permission = build_permission(config=PermissionConfig(policy_root=str(ROOT)))
    permission.runtime.start()
    return permission


def _evaluate(system, role, tool):
    subject = PermissionSubject(
        subject_id="U", tenant_id="company_A", roles=frozenset({role}),
    )
    resource = PermissionResource("tool", tool, "company_A")
    request = PermissionRequest(
        "R", subject, resource, "execute",
        PermissionEnvironment(attributes={"business_freeze": False}),
    )
    return system.evaluate(request)


def _legacy_allows(role, tool):
    allowed = _LEGACY.get(role, set())
    if allowed == "*":
        return True
    return tool in allowed


@pytest.mark.parametrize("role", ["sales", "manager", "admin", "unknown"])
@pytest.mark.parametrize("tool", _TOOLS)
def test_legacy_parity(system, role, tool):
    expected_allow = _legacy_allows(role, tool)
    decision = _evaluate(system, role, tool)
    assert (decision.decision is Decision.ALLOW) == expected_allow
