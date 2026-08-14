"""Operator implementations — four-valued logic (TRUE/FALSE/UNKNOWN/ERROR)."""

import math
from enum import Enum

from app.permission.evaluation.field_resolver import MISSING
from app.permission.models.scope import PermissionScope


class TruthValue(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


_LEVEL_VALUES = {f"P{i}": i for i in range(1, 11)}


def _is_number(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    return False


def _is_collection(value):
    return isinstance(value, (list, tuple, set, frozenset))


def _any_missing(*values):
    return any(v is MISSING or v is None for v in values)


# --- equality ---

def _equals(left, right):
    if _any_missing(left, right):
        return TruthValue.UNKNOWN
    return TruthValue.TRUE if left == right else TruthValue.FALSE


def _not_equals(left, right):
    if _any_missing(left, right):
        return TruthValue.UNKNOWN
    return TruthValue.TRUE if left != right else TruthValue.FALSE


# --- membership ---

def _in(left, right):
    if _any_missing(left, right):
        return TruthValue.UNKNOWN
    if not _is_collection(right):
        return TruthValue.ERROR
    return TruthValue.TRUE if left in right else TruthValue.FALSE


def _not_in(left, right):
    if _any_missing(left, right):
        return TruthValue.UNKNOWN
    if not _is_collection(right):
        return TruthValue.ERROR
    return TruthValue.TRUE if left not in right else TruthValue.FALSE


def _contains(left, right):
    if _any_missing(left, right):
        return TruthValue.UNKNOWN
    if not _is_collection(left):
        return TruthValue.ERROR
    return TruthValue.TRUE if right in left else TruthValue.FALSE


def _contains_any(left, right):
    if _any_missing(left, right):
        return TruthValue.UNKNOWN
    if not _is_collection(left) or not _is_collection(right):
        return TruthValue.ERROR
    return TruthValue.TRUE if set(left) & set(right) else TruthValue.FALSE


def _contains_all(left, right):
    if _any_missing(left, right):
        return TruthValue.UNKNOWN
    if not _is_collection(left) or not _is_collection(right):
        return TruthValue.ERROR
    return TruthValue.TRUE if set(right).issubset(set(left)) else TruthValue.FALSE


# --- numeric ---

def _numeric(left, right, compare):
    if _any_missing(left, right):
        return TruthValue.UNKNOWN
    if not _is_number(left) or not _is_number(right):
        return TruthValue.ERROR
    return TruthValue.TRUE if compare(left, right) else TruthValue.FALSE


def _gt(left, right):
    return _numeric(left, right, lambda a, b: a > b)


def _gte(left, right):
    return _numeric(left, right, lambda a, b: a >= b)


def _lt(left, right):
    return _numeric(left, right, lambda a, b: a < b)


def _lte(left, right):
    return _numeric(left, right, lambda a, b: a <= b)


# --- professional level ---

def _level(left, right, compare):
    if _any_missing(left, right):
        return TruthValue.UNKNOWN
    left_v = _LEVEL_VALUES.get(left)
    right_v = _LEVEL_VALUES.get(right)
    if left_v is None or right_v is None:
        return TruthValue.ERROR
    return TruthValue.TRUE if compare(left_v, right_v) else TruthValue.FALSE


def _gte_level(left, right):
    return _level(left, right, lambda a, b: a >= b)


def _lte_level(left, right):
    return _level(left, right, lambda a, b: a <= b)


# --- existence ---

def _exists(left, right):
    return TruthValue.TRUE if left is not MISSING else TruthValue.FALSE


def _not_exists(left, right):
    return TruthValue.TRUE if left is MISSING else TruthValue.FALSE


# --- scope ---

def _scope_contains(left, right, dimension):
    if not isinstance(left, PermissionScope):
        return TruthValue.ERROR
    if right is MISSING or right is None:
        return TruthValue.UNKNOWN
    values = left.values_for(dimension)
    if not values:
        return TruthValue.FALSE  # no grant => not authorized
    return TruthValue.TRUE if right in values else TruthValue.FALSE


_OPERATORS = {
    "equals": _equals,
    "not_equals": _not_equals,
    "in": _in,
    "not_in": _not_in,
    "contains": _contains,
    "contains_any": _contains_any,
    "contains_all": _contains_all,
    "gt": _gt,
    "gte": _gte,
    "lt": _lt,
    "lte": _lte,
    "gte_level": _gte_level,
    "lte_level": _lte_level,
    "exists": _exists,
    "not_exists": _not_exists,
    "scope_contains": _scope_contains,
}


def apply(operator, left, right, dimension=None):
    fn = _OPERATORS.get(operator)
    if fn is None:
        return TruthValue.ERROR
    if operator == "scope_contains":
        return fn(left, right, dimension)
    return fn(left, right)
