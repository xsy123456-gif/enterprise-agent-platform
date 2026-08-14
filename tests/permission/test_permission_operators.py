"""Operator + four-valued condition semantics tests."""

from app.permission.evaluation.field_resolver import MISSING
from app.permission.evaluation.native import NativePolicyEvaluator
from app.permission.evaluation.operators import TruthValue, apply
from app.permission.models.condition import (
    AllCondition,
    AnyCondition,
    AtomicCondition,
    NotCondition,
)
from app.permission.models.scope import PermissionScope, ScopeGrant


def test_equals_true_false_unknown():
    assert apply("equals", "a", "a") is TruthValue.TRUE
    assert apply("equals", "a", "b") is TruthValue.FALSE
    assert apply("equals", MISSING, "a") is TruthValue.UNKNOWN
    assert apply("equals", None, "a") is TruthValue.UNKNOWN


def test_in_true_false_error():
    assert apply("in", "a", ["a", "b"]) is TruthValue.TRUE
    assert apply("in", "c", ["a", "b"]) is TruthValue.FALSE
    assert apply("in", "a", "not-a-collection") is TruthValue.ERROR
    assert apply("in", MISSING, ["a"]) is TruthValue.UNKNOWN


def test_contains():
    assert apply("contains", frozenset({"a", "b"}), "a") is TruthValue.TRUE
    assert apply("contains", frozenset({"a"}), "b") is TruthValue.FALSE


def test_numeric_comparison_rejects_non_number():
    assert apply("gte", 3, 2) is TruthValue.TRUE
    assert apply("gte", "abc", 10) is TruthValue.ERROR
    assert apply("gte", True, 1) is TruthValue.ERROR  # bool is not a number


def test_level_comparison():
    assert apply("gte_level", "P4", "P3") is TruthValue.TRUE
    assert apply("gte_level", "P2", "P3") is TruthValue.FALSE
    assert apply("gte_level", "P11", "P3") is TruthValue.ERROR
    assert apply("gte_level", None, "P3") is TruthValue.UNKNOWN


def test_exists_not_exists():
    assert apply("exists", "x", None) is TruthValue.TRUE
    assert apply("exists", MISSING, None) is TruthValue.FALSE
    assert apply("not_exists", MISSING, None) is TruthValue.TRUE


def test_scope_contains():
    scope = PermissionScope(grants=(ScopeGrant("business.store", frozenset({"JP01"})),))
    assert apply("scope_contains", scope, "JP01", "business.store") is TruthValue.TRUE
    assert apply("scope_contains", scope, "US01", "business.store") is TruthValue.FALSE
    # missing dimension -> no grant -> FALSE
    assert apply("scope_contains", scope, "JP01", "geo.region") is TruthValue.FALSE
    # missing right value -> UNKNOWN
    assert apply("scope_contains", scope, MISSING, "business.store") is TruthValue.UNKNOWN


class _FourStateEvaluator(NativePolicyEvaluator):
    pass


def test_not_unknown_is_unknown():
    ev = _FourStateEvaluator()
    node = NotCondition(AtomicCondition("subject.department_id", "equals", "x"))
    result = ev._eval_condition(node, _request(department_id=None))
    assert result is TruthValue.UNKNOWN


def test_all_with_unknown():
    ev = _FourStateEvaluator()
    node = AllCondition((
        AtomicCondition("subject.department_id", "equals", "operations"),
        AtomicCondition("subject.professional_level", "gte_level", "P3"),
    ))
    assert ev._eval_condition(node, _request(department_id="operations", level=None)) is TruthValue.UNKNOWN


def test_any_with_unknown_and_true():
    ev = _FourStateEvaluator()
    node = AnyCondition((
        AtomicCondition("subject.department_id", "equals", "operations"),
        AtomicCondition("subject.professional_level", "gte_level", "P3"),
    ))
    assert ev._eval_condition(node, _request(department_id="operations", level=None)) is TruthValue.TRUE


def _request(department_id=None, level=None):
    from app.permission.models.environment import PermissionEnvironment
    from app.permission.models.request import PermissionRequest
    from app.permission.models.resource import PermissionResource
    from app.permission.models.subject import PermissionSubject

    subject = PermissionSubject(
        subject_id="u", tenant_id="t", roles=frozenset(),
        department_id=department_id, professional_level=level,
    )
    resource = PermissionResource("r", "id", "t")
    return PermissionRequest("r1", subject, resource, "read", PermissionEnvironment())
