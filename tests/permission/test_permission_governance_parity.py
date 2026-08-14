"""Lifecycle authorization tests: system principal + management department.

The legacy PolicyDecisionEngine is removed; lifecycle authorization is now
decided by the Permission foundation via the security integration layer.
"""

from pathlib import Path

import pytest

from app.identity import build_identity
from app.identity.providers.local_file import LocalFileIdentityProvider
from app.integrations.security import TrustedPrincipal, build_security_integration
from app.permission import PermissionConfig, build_permission
from app.runtime.governance.gate import AllowAllGovernancePolicy, GovernanceGate

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def security():
    identity = build_identity(
        provider=LocalFileIdentityProvider(str(ROOT / "data" / "identity"))
    )
    permission = build_permission(
        config=PermissionConfig(policy_root=str(ROOT / "data" / "permission" / "policies"))
    )
    permission.runtime.start()
    return build_security_integration(
        identity_service=identity.service,
        permission_service=permission.service,
        governance_gate=GovernanceGate(AllowAllGovernancePolicy()),
    )


def test_system_principal_can_do_lifecycle(security):
    bootstrap = TrustedPrincipal("platform.bootstrap", source="system")
    for action in ["create", "submit_review", "approve", "activate",
                   "suspend", "deprecate", "archive"]:
        assert security.lifecycle_authorization.authorize(
            bootstrap, action, "sales_agent", "0.2"
        ) is True


def test_management_can_do_lifecycle(security):
    executive = TrustedPrincipal("U008")  # management executive
    for action in ["create", "approve", "activate", "suspend", "deprecate"]:
        assert security.lifecycle_authorization.authorize(
            executive, action, "sales_agent", "0.2"
        ) is True


def test_other_department_cannot_do_lifecycle(security):
    ads = TrustedPrincipal("U003")  # advertising
    assert security.lifecycle_authorization.authorize(
        ads, "activate", "sales_agent", "0.2"
    ) is False
