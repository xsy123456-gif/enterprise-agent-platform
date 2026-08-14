"""Subject adapter tests: explicit mapping, no inference, scope determinism."""

from pathlib import Path

from app.identity import build_identity
from app.identity.providers.local_file import LocalFileIdentityProvider
from app.integrations.security import (
    IdentityPermissionSubjectAdapter,
    TrustedPrincipal,
    TrustedSubjectResolver,
)

ROOT = Path(__file__).resolve().parents[2]


def _resolver():
    identity = build_identity(
        provider=LocalFileIdentityProvider(str(ROOT / "data" / "identity"))
    )
    return TrustedSubjectResolver(identity.service)


def test_map_basic_fields():
    subject = _resolver().resolve(TrustedPrincipal("U003"))
    assert subject.subject_id == "U003"
    assert subject.department_id == "advertising"
    assert subject.position_id == "advertising_specialist"
    assert subject.professional_level == "P4"
    assert subject.security_clearance == "internal"
    assert "advertising_operator" in subject.roles


def test_scope_mapping_to_dimensions():
    subject = _resolver().resolve(TrustedPrincipal("U004"))
    store_dim = next(g.dimension for g in subject.scopes.grants
                     if g.dimension == "business.store")
    store_values = subject.scopes.values_for("business.store")
    assert set(store_values) == {"JP01", "JP02"}


def test_no_inference_from_level():
    # A P9 user with no roles must still have no roles (no auto admin).
    identity = build_identity(
        provider=LocalFileIdentityProvider(str(ROOT / "data" / "identity"))
    )
    from app.identity.models.user import UserIdentity
    from app.identity.ports.provider import IdentityProviderPort
    from app.identity.models.organization import Organization
    from app.identity.models.department import Department
    from app.identity.models.position import Position
    from app.identity.api.service import IdentityService
    from app.identity.validation.validator import IdentityValidator
    from app.identity.context.builder import AccessContextBuilder

    class P9NoRoleProvider(IdentityProviderPort):
        def get_user(self, user_id):
            return UserIdentity("U9", "company_A", "x", "active", "company_A",
                                "management", "executive", "P9",
                                role_ids=(), scope_ids=(),
                                security_clearance="confidential")
        def get_organization(self, oid):
            return Organization("company_A", "company_A", "Demo")
        def get_department(self, did):
            return Department("management", "company_A", "管理层")
        def get_position(self, pid):
            return Position("executive", "company_A", "管理层")
        def get_roles(self, rids):
            return []
        def get_scopes(self, sids):
            return []

    service = IdentityService(P9NoRoleProvider(), IdentityValidator(),
                              AccessContextBuilder())
    resolver = TrustedSubjectResolver(service)
    subject = resolver.resolve(TrustedPrincipal("U9"))
    assert subject.roles == frozenset()
    assert subject.professional_level == "P9"


def test_scope_mapping_is_order_independent():
    a = _resolver().resolve(TrustedPrincipal("U004"))
    b = _resolver().resolve(TrustedPrincipal("U004"))
    assert a.scopes.to_dict() == b.scopes.to_dict()
