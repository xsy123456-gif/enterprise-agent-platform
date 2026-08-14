"""Fail-closed, determinism, and dependency-boundary tests."""

import ast
from pathlib import Path

import pytest

from app.permission import (
    Decision,
    PermissionConfig,
    PermissionEnvironment,
    PermissionRequest,
    PermissionResource,
    PermissionSubject,
    ReasonCode,
    build_permission,
)
from app.permission.models.policy import PermissionPolicy, PolicyScope, PolicyTarget
from app.permission.policy.snapshot import build_snapshot

ROOT = Path(__file__).resolve().parents[2] / "data" / "permission" / "policies"


@pytest.fixture(scope="module")
def system():
    permission = build_permission(config=PermissionConfig(policy_root=str(ROOT)))
    permission.runtime.start()
    return permission


def _request(**subject_kw):
    subject = PermissionSubject(
        subject_id=subject_kw.get("subject_id", "U1"),
        tenant_id="company_A",
        roles=frozenset(subject_kw.get("roles", ())),
        department_id=subject_kw.get("department_id"),
        professional_level=subject_kw.get("professional_level"),
        attributes={"employment_type": "full_time"},
    )
    resource = PermissionResource("campaign", "C1", "company_A",
                                  attributes={"store_id": "JP01"})
    return PermissionRequest(
        "R1", subject, resource, "update",
        PermissionEnvironment(attributes={"business_freeze": False}),
    )


def test_invalid_request_is_denied(system):
    request = _request(subject_id="")  # empty subject_id
    decision = system.evaluate(request)
    assert decision.decision is Decision.DENY
    assert decision.reason_code is ReasonCode.DENY_INVALID_REQUEST


def test_no_snapshot_is_unavailable():
    from app.permission.providers.local_file import LocalFilePolicyProvider

    permission = build_permission(
        config=PermissionConfig(policy_root=str(ROOT)),
        provider=LocalFilePolicyProvider(str(ROOT)),
    )
    # not started -> no snapshot
    decision = permission.evaluate(_request())
    assert decision.reason_code is ReasonCode.DENY_POLICY_UNAVAILABLE


def test_deterministic_evaluation(system):
    request = _request(department_id="operations", professional_level="P4")
    d1 = system.evaluate(request)
    d2 = system.evaluate(request)
    assert d1.decision is d2.decision
    assert d1.reason_code is d2.reason_code
    assert d1.matched_policy_refs == d2.matched_policy_refs
    assert d1.policy_set_version == d2.policy_set_version
    assert d1.decision_id != d2.decision_id  # decision_id may differ


def _sample_policy(pid, order_field):
    return PermissionPolicy(
        policy_id=pid, version=1, status="active",
        scope=PolicyScope("platform"), effect="allow",
        target=PolicyTarget(
            resource_types=frozenset({"a", "b"}),  # frozenset is unordered
        ),
    )


def test_policy_set_version_is_order_independent():
    p1 = _sample_policy("p1", 1)
    p2 = _sample_policy("p2", 2)
    v1 = build_snapshot([p1, p2]).policy_set_version
    v2 = build_snapshot([p2, p1]).policy_set_version
    assert v1 == v2


def _permission_imports():
    root = Path(__file__).resolve().parents[2] / "app" / "permission"
    imports = set()
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
    return imports


def test_permission_does_not_import_other_domains():
    forbidden = (
        "app.identity", "app.knowledge", "app.memory", "app.tools",
        "app.agents", "app.governance", "app.runtime",
    )
    for name in _permission_imports():
        assert not name.startswith(forbidden), f"permission imports {name}"
