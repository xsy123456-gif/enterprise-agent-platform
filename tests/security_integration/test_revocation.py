"""Identity revocation + fail-closed tests (no legacy fallback)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.identity import build_identity
from app.identity.models.department import Department
from app.identity.models.organization import Organization
from app.identity.models.position import Position
from app.identity.models.user import UserIdentity
from app.identity.ports.provider import IdentityProviderPort
from app.integrations.security import TrustedPrincipal, build_security_integration
from app.permission import PermissionConfig, build_permission
from app.runtime.governance.gate import AllowAllGovernancePolicy, GovernanceGate

ROOT = Path(__file__).resolve().parents[2]


class _MutableIdentityProvider(IdentityProviderPort):
    """A provider whose user status/scope can be changed at runtime."""

    def __init__(self, status="active", stores=("JP01", "JP02")):
        self.status = status
        self.stores = stores

    def get_user(self, user_id):
        return UserIdentity(
            user_id, "company_A", "x", self.status, "company_A", "operations",
            "product_operator", "P4", role_ids=("product_operator",),
            scope_ids=("S1",) if self.stores else (),
            security_clearance="internal",
        )

    def get_organization(self, oid):
        return Organization("company_A", "company_A", "Demo")

    def get_department(self, did):
        return Department("operations", "company_A", "运营部")

    def get_position(self, pid):
        return Position("product_operator", "company_A", "商品运营")

    def get_roles(self, rids):
        from app.identity.models.role import Role
        return [Role("product_operator", "company_A", "商品运营")]

    def get_scopes(self, sids):
        if not self.stores:
            return []
        from app.identity.models.scope import BusinessScope
        return [BusinessScope("S1", "company_A", stores=tuple(self.stores))]


def _sec(identity, permission):
    return build_security_integration(
        identity_service=identity.service,
        permission_service=permission.service,
        governance_gate=GovernanceGate(AllowAllGovernancePolicy()),
    )


def _permission():
    p = build_permission(
        config=PermissionConfig(policy_root=str(ROOT / "data" / "permission" / "policies"))
    )
    p.runtime.start()
    return p


def _tool_req(user_id="U1", tenant_id="company_A", arguments=None):
    return SimpleNamespace(
        user_id=user_id, tenant_id=tenant_id, tool_name="crm_query",
        agent_id="sales_agent", execution_id="e1", request_id="r1",
        arguments=arguments,
    )


def test_suspension_takes_effect_on_next_tool_call():
    provider = _MutableIdentityProvider(status="active")
    identity = build_identity(provider=provider)
    sec = _sec(identity, _permission())

    # Active: allowed.
    allowed, _ = sec.tool_gate.check(_tool_req())
    assert allowed is True

    # Suspend mid-execution: next tool call is denied.
    provider.status = "suspended"
    allowed, decision = sec.tool_gate.check(_tool_req())
    assert allowed is False
    assert "principal" in decision.reason.lower()


def test_scope_change_takes_effect_on_next_tool_call():
    provider = _MutableIdentityProvider(stores=("JP01", "JP02"))
    identity = build_identity(provider=provider)
    sec = _sec(identity, _permission())

    # JP02 within scope -> allowed.
    allowed, _ = sec.tool_gate.check(_tool_req(arguments={"store_id": "JP02"}))
    assert allowed is True

    # Scope shrinks to JP01 -> JP02 now denied.
    provider.stores = ("JP01",)
    allowed, _ = sec.tool_gate.check(_tool_req(arguments={"store_id": "JP02"}))
    assert allowed is False


def test_policy_revocation_takes_effect_on_next_tool_call():
    from app.permission.ports.policy_provider import PolicyProviderPort
    from app.permission.policy.parser import parse_policies
    import yaml

    class _MutablePolicyProvider(PolicyProviderPort):
        def __init__(self, policies):
            self.policies = policies

        def load_policies(self):
            return list(self.policies)

    allow_policy = parse_policies(yaml.safe_load("""
        policies:
          - policy_id: test.tool.execute
            version: 1
            status: active
            scope:
              type: tenant
              tenant_id: company_A
            effect: allow
            target:
              resource_types: [tool]
              actions: [execute]
            condition:
              field: subject.department_id
              operator: equals
              value: operations
    """))
    provider = _MutablePolicyProvider(allow_policy)
    permission = build_permission(provider=provider)
    permission.runtime.start()

    identity = build_identity(provider=_MutableIdentityProvider())
    sec = _sec(identity, permission)

    # Policy allows -> tool allowed.
    allowed, _ = sec.tool_gate.check(_tool_req())
    assert allowed is True

    # Policy reloaded with a deny -> next tool denied.
    deny_policy = parse_policies(yaml.safe_load("""
        policies:
          - policy_id: test.tool.deny
            version: 1
            status: active
            scope:
              type: tenant
              tenant_id: company_A
            effect: deny
            target:
              resource_types: [tool]
              actions: [execute]
            condition:
              field: subject.department_id
              operator: equals
              value: operations
    """))
    provider.policies = deny_policy
    assert permission.runtime.reload() is True
    allowed, _ = sec.tool_gate.check(_tool_req())
    assert allowed is False
