"""Identity validation tests: fail-closed, cross-tenant, status, level/clearance."""

import pytest

from app.identity import (
    BusinessScope,
    Department,
    IdentityNotFoundError,
    IdentityService,
    IdentityValidationError,
    Organization,
    Position,
    Role,
    UserIdentity,
)
from app.identity.ports.provider import IdentityProviderPort


class FakeIdentityProvider(IdentityProviderPort):
    def __init__(self, users=None, organizations=None, departments=None,
                 positions=None, roles=None, scopes=None):
        self.users = users or {}
        self.organizations = organizations or {}
        self.departments = departments or {}
        self.positions = positions or {}
        self.roles = roles or {}
        self.scopes = scopes or {}

    def get_user(self, user_id):
        user = self.users.get(user_id)
        if user is None:
            raise IdentityNotFoundError(f"user not found: {user_id}")
        return user

    def get_organization(self, organization_id):
        e = self.organizations.get(organization_id)
        if e is None:
            raise IdentityNotFoundError(f"organization not found: {organization_id}")
        return e

    def get_department(self, department_id):
        e = self.departments.get(department_id)
        if e is None:
            raise IdentityNotFoundError(f"department not found: {department_id}")
        return e

    def get_position(self, position_id):
        e = self.positions.get(position_id)
        if e is None:
            raise IdentityNotFoundError(f"position not found: {position_id}")
        return e

    def get_roles(self, role_ids):
        roles = []
        for role_id in role_ids:
            role = self.roles.get(role_id)
            if role is None:
                raise IdentityNotFoundError(f"role not found: {role_id}")
            roles.append(role)
        return roles

    def get_scopes(self, scope_ids):
        scopes = []
        for scope_id in scope_ids:
            scope = self.scopes.get(scope_id)
            if scope is None:
                raise IdentityNotFoundError(f"scope not found: {scope_id}")
            scopes.append(scope)
        return scopes


def _base_entities(tenant="company_A"):
    return {
        "organizations": {"company_A": Organization("company_A", tenant, "Demo")},
        "departments": {"operations": Department("operations", tenant, "运营部")},
        "positions": {"product_operator": Position("product_operator", tenant, "商品运营")},
        "roles": {"product_operator": Role("product_operator", tenant, "商品运营")},
        "scopes": {"JP01": BusinessScope("JP01", tenant, stores=("JP01",), regions=("JP",))},
    }


def _user(tenant="company_A", **overrides):
    data = dict(
        user_id="U1", tenant_id=tenant, name="张三", status="active",
        organization_id="company_A", department_id="operations",
        position_id="product_operator", professional_level_id="P3",
        role_ids=("product_operator",), scope_ids=("JP01",),
        security_clearance="internal",
    )
    data.update(overrides)
    return UserIdentity(**data)


def _service(user, **entities_overrides):
    entities = _base_entities(user.tenant_id)
    entities.update(entities_overrides)
    provider = FakeIdentityProvider(users={user.user_id: user}, **entities)
    return IdentityService(provider)


def test_suspended_user_is_blocked():
    service = _service(_user(status="suspended"))
    with pytest.raises(IdentityValidationError):
        service.build_access_context("U1")


def test_invalid_level_is_rejected():
    service = _service(_user(professional_level_id="P11"))
    with pytest.raises(IdentityValidationError):
        service.build_access_context("U1")


def test_invalid_clearance_is_rejected():
    service = _service(_user(security_clearance="top_secret"))
    with pytest.raises(IdentityValidationError):
        service.build_access_context("U1")


def test_cross_tenant_scope_is_rejected():
    user = _user(tenant="company_A", scope_ids=("JP01",))
    entities = _base_entities("company_A")
    entities["scopes"] = {
        "JP01": BusinessScope("JP01", "company_B", stores=("JP01",), regions=("JP",))
    }
    provider = FakeIdentityProvider(users={user.user_id: user}, **entities)
    service = IdentityService(provider)
    with pytest.raises(IdentityValidationError):
        service.build_access_context("U1")


def test_unknown_role_reference_is_rejected():
    service = _service(_user(role_ids=("nonexistent_role",)))
    with pytest.raises(IdentityNotFoundError):
        service.build_access_context("U1")


def test_level_and_clearance_are_independent():
    # Two P6 users with different clearances build successfully.
    internal = _user(user_id="A", professional_level_id="P6",
                     security_clearance="internal")
    confidential = _user(user_id="B", professional_level_id="P6",
                         security_clearance="confidential")

    ctx_a = _service(internal).build_access_context("A")
    ctx_b = _service(confidential).build_access_context("B")
    assert ctx_a.professional_level == "P6"
    assert ctx_b.professional_level == "P6"
    assert ctx_a.security_clearance == "internal"
    assert ctx_b.security_clearance == "confidential"
