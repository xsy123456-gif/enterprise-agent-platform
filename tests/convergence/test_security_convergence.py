"""Phase 18.7 Security Convergence tests."""

import pytest

from app.composition.security import (
    ApplicationStartupError,
    PRINCIPAL_LOCAL,
    SecurityConfigValidator,
)
from app.runtime.governance.gate import AllowAllGovernancePolicy
from app.memory.ports.authorization import (
    AllowAllMemoryAuthorizationProvider,
    DenyByDefaultMemoryAuthorizationProvider,
)


class _StrictPolicy:
    pass


def test_production_allow_all_is_violation():
    validator = SecurityConfigValidator(
        "production", governance_policy=AllowAllGovernancePolicy(),
        memory_authorization=AllowAllMemoryAuthorizationProvider(),
        principal_source=PRINCIPAL_LOCAL,
    )
    violations = validator.violations()
    assert any("AllowAllGovernancePolicy" in v for v in violations)
    assert any("AllowAllMemoryAuthorizationProvider" in v for v in violations)
    assert any("local principal" in v for v in violations)


def test_production_secure_config_passes():
    validator = SecurityConfigValidator(
        "production", governance_policy=_StrictPolicy(),
        memory_authorization=DenyByDefaultMemoryAuthorizationProvider(),
        principal_source="external",
    )
    assert validator.violations() == []
    validator.assert_secure()


def test_development_allow_all_is_allowed():
    validator = SecurityConfigValidator(
        "development", governance_policy=AllowAllGovernancePolicy(),
        memory_authorization=AllowAllMemoryAuthorizationProvider(),
        principal_source=PRINCIPAL_LOCAL,
    )
    assert validator.violations() == []
    validator.assert_secure()


def test_production_insecure_startup_fails_closed():
    validator = SecurityConfigValidator(
        "production", governance_policy=AllowAllGovernancePolicy(),
        memory_authorization=AllowAllMemoryAuthorizationProvider(),
        principal_source=PRINCIPAL_LOCAL,
    )
    with pytest.raises(ApplicationStartupError):
        validator.assert_secure()


def test_enterprise_application_production_fails_closed():
    from app.composition.enterprise import build_enterprise_application
    # build_application currently composes AllowAll + local identity, so a
    # production build must fail startup (not silently run insecure).
    with pytest.raises(ApplicationStartupError):
        build_enterprise_application("production")
