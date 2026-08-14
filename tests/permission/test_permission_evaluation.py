"""Permission evaluation tests against the enterprise policy fixtures."""

from pathlib import Path

import pytest

from app.permission import (
    Decision,
    PermissionConfig,
    PermissionEnvironment,
    PermissionRequest,
    PermissionResource,
    PermissionScope,
    PermissionSubject,
    ReasonCode,
    ScopeGrant,
    build_permission,
)

ROOT = Path(__file__).resolve().parents[2] / "data" / "permission" / "policies"


@pytest.fixture(scope="module")
def system():
    permission = build_permission(
        config=PermissionConfig(policy_root=str(ROOT))
    )
    assert permission.runtime.start()
    return permission


def _subject(**kw):
    attributes = kw.get("attributes", {"employment_type": "full_time"})
    return PermissionSubject(
        subject_id=kw.get("subject_id", "U1"),
        tenant_id=kw.get("tenant_id", "company_A"),
        roles=frozenset(kw.get("roles", ())),
        department_id=kw.get("department_id"),
        position_id=kw.get("position_id"),
        professional_level=kw.get("professional_level"),
        security_clearance=kw.get("security_clearance"),
        scopes=kw.get("scopes", PermissionScope()),
        attributes=attributes,
    )


def _resource(rtype, rid, **attrs):
    return PermissionResource(
        resource_type=rtype, resource_id=rid, tenant_id="company_A",
        attributes=attrs,
    )


def _evaluate(system, subject, resource, action, env=None):
    request = PermissionRequest(
        request_id="R1", subject=subject, resource=resource, action=action,
        environment=env if env is not None else PermissionEnvironment(
            attributes={"business_freeze": False}
        ),
    )
    return system.evaluate(request)


def test_rbac_role_contains(system):
    subject = _subject(roles=("advertising_operator",))
    decision = _evaluate(system, subject, _resource("report", "X"), "read")
    assert decision.decision is Decision.ALLOW


def test_department_and_level_abac(system):
    subject = _subject(department_id="operations", professional_level="P4")
    decision = _evaluate(system, subject, _resource("campaign", "C1"), "update")
    assert decision.decision is Decision.ALLOW


def test_department_abac_denies_low_level(system):
    subject = _subject(department_id="operations", professional_level="P2")
    decision = _evaluate(
        system, subject, _resource("campaign", "C1", store_id="JP01"), "update"
    )
    assert decision.decision is Decision.DENY
    assert decision.reason_code is ReasonCode.DENY_NO_MATCH


def test_scope_contains_own_store(system):
    subject = _subject(
        roles=("advertising_operator",),
        scopes=PermissionScope(grants=(ScopeGrant("business.store", frozenset({"JP01"})),)),
    )
    decision = _evaluate(
        system, subject, _resource("campaign", "C1", store_id="JP01"), "update"
    )
    assert decision.decision is Decision.ALLOW


def test_scope_contains_denies_other_store(system):
    subject = _subject(
        roles=("advertising_operator",),
        scopes=PermissionScope(grants=(ScopeGrant("business.store", frozenset({"JP01"})),)),
    )
    decision = _evaluate(
        system, subject, _resource("campaign", "C1", store_id="US01"), "update"
    )
    assert decision.decision is Decision.DENY


def test_cross_tenant_is_denied(system):
    subject = _subject()
    resource = PermissionResource(
        resource_type="campaign", resource_id="C1", tenant_id="company_B",
    )
    decision = _evaluate(system, subject, resource, "update")
    assert decision.decision is Decision.DENY
    assert decision.reason_code is ReasonCode.DENY_TENANT_MISMATCH


def test_explicit_deny_overrides_allow(system):
    subject = _subject(department_id="operations", professional_level="P4")
    env = PermissionEnvironment(attributes={"business_freeze": True})
    decision = _evaluate(
        system, subject, _resource("campaign", "C1"), "update", env=env
    )
    assert decision.decision is Decision.DENY
    assert decision.reason_code is ReasonCode.DENY_EXPLICIT


def test_missing_fact_indeterminate_deny(system):
    subject = _subject(
        department_id="operations", professional_level="P4", attributes={}
    )
    # no employment_type attribute -> contractor deny policy is UNKNOWN
    decision = _evaluate(system, subject, _resource("campaign", "C1"), "update")
    assert decision.decision is Decision.DENY
    assert decision.reason_code is ReasonCode.DENY_INDETERMINATE
