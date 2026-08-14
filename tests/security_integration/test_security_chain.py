"""Security chain tests: fail-closed, ordering, revocation."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.identity import build_identity
from app.identity.providers.local_file import LocalFileIdentityProvider
from app.integrations.security import (
    TrustedPrincipal,
    build_security_integration,
)
from app.permission import PermissionConfig, build_permission
from app.runtime.governance.gate import (
    AllowAllGovernancePolicy,
    GovernanceDecision,
    GovernanceGate,
    GovernanceResult,
)

ROOT = Path(__file__).resolve().parents[2]


class _SpyGovernanceGate:
    def __init__(self, result_allowed=True):
        self.calls = 0
        self.result_allowed = result_allowed

    def check(self, request):
        self.calls += 1
        if self.result_allowed:
            return True, GovernanceResult(GovernanceDecision.ALLOW, "ok")
        return False, GovernanceResult(GovernanceDecision.DENY, "blocked")


@pytest.fixture(scope="module")
def identity():
    return build_identity(
        provider=LocalFileIdentityProvider(str(ROOT / "data" / "identity"))
    )


@pytest.fixture(scope="module")
def permission():
    p = build_permission(
        config=PermissionConfig(policy_root=str(ROOT / "data" / "permission" / "policies"))
    )
    p.runtime.start()
    return p


def _sec(identity, permission, governance_gate):
    return build_security_integration(
        identity_service=identity.service,
        permission_service=permission.service,
        governance_gate=governance_gate,
    )


def _tool_req(user_id, tenant_id="company_A", tool="crm_query"):
    return SimpleNamespace(
        user_id=user_id, tenant_id=tenant_id, tool_name=tool,
        agent_id="sales_agent", execution_id="e1", request_id="r1",
    )


def test_agent_admission_allow_and_deny(identity, permission):
    sec = _sec(identity, permission, GovernanceGate(AllowAllGovernancePolicy()))
    allowed = sec.admission.allowed(
        TrustedPrincipal("U001"), "sales_agent", "0.2", "company_A"
    )
    assert allowed is True
    denied = sec.admission.allowed(
        TrustedPrincipal("U005"), "sales_agent", "0.2", "company_A"
    )
    assert denied is False


def test_tool_gate_permission_deny_skips_governance(identity, permission):
    spy = _SpyGovernanceGate()
    sec = _sec(identity, permission, spy)
    # U006 (finance) is not in the tool-execution department list -> DENY.
    allowed, decision = sec.tool_gate.check(_tool_req("U006"))
    assert allowed is False
    assert spy.calls == 0  # Governance never called on permission DENY


def test_tool_gate_permission_allow_calls_governance(identity, permission):
    spy = _SpyGovernanceGate()
    sec = _sec(identity, permission, spy)
    allowed, decision = sec.tool_gate.check(_tool_req("U001"))
    assert allowed is True
    assert spy.calls == 1


def test_tool_gate_governance_deny_blocks_execution(identity, permission):
    spy = _SpyGovernanceGate(result_allowed=False)
    sec = _sec(identity, permission, spy)
    allowed, decision = sec.tool_gate.check(_tool_req("U001"))
    assert allowed is False
    assert spy.calls == 1


def test_unknown_principal_denies(identity, permission):
    sec = _sec(identity, permission, GovernanceGate(AllowAllGovernancePolicy()))
    allowed, decision = sec.tool_gate.check(_tool_req("UNKNOWN"))
    assert allowed is False


def test_tenant_mismatch_denies(identity, permission):
    sec = _sec(identity, permission, GovernanceGate(AllowAllGovernancePolicy()))
    allowed, decision = sec.tool_gate.check(
        _tool_req("U001", tenant_id="company_B")
    )
    assert allowed is False
    assert "tenant" in decision.reason.lower()
