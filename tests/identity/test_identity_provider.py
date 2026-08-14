"""Identity provider + access context tests against the enterprise dataset."""

from pathlib import Path

from app.identity import build_identity, SecurityClearance, ProfessionalLevel
from app.identity.providers.local_file import LocalFileIdentityProvider

ROOT = Path(__file__).resolve().parents[2] / "data" / "identity"


def _system():
    return build_identity(provider=LocalFileIdentityProvider(str(ROOT)))


def test_provider_loads_enterprise_data():
    provider = LocalFileIdentityProvider(str(ROOT))
    health = provider.health()
    assert health["users"] == 8
    assert health["organizations"] == 1
    assert health["departments"] == 5


def test_access_context_for_u003():
    ctx = _system().build_access_context("U003")
    assert ctx.department_id == "advertising"
    assert ctx.position_id == "advertising_specialist"
    assert ctx.professional_level == "P4"
    assert ctx.security_clearance == "internal"
    assert "JP01" in ctx.business_scope.stores
    assert "advertising_operator" in ctx.roles


def test_multi_store_scope_for_u004():
    ctx = _system().build_access_context("U004")
    assert set(ctx.business_scope.stores) == {"JP01", "JP02"}
    assert ctx.security_clearance == "confidential"
    assert "advertising_approver" in ctx.roles


def test_multi_region_scope_for_u008():
    ctx = _system().build_access_context("U008")
    assert set(ctx.business_scope.stores) == {"JP01", "JP02", "US01"}
    assert set(ctx.business_scope.regions) == {"JP", "US"}
    assert ctx.professional_level == "P9"


def test_identity_version_is_stable():
    system = _system()
    c1 = system.build_access_context("U001")
    c2 = system.build_access_context("U001")
    assert c1.identity_version == c2.identity_version
    assert c1.identity_version


def test_identity_version_differs_across_users():
    system = _system()
    assert (
        system.build_access_context("U001").identity_version
        != system.build_access_context("U004").identity_version
    )


def test_levels_and_clearance_are_platform_enums():
    assert len(ProfessionalLevel.values()) == 10
    assert SecurityClearance.values() == [
        "public", "internal", "confidential", "restricted",
    ]
