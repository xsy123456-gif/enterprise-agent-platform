"""WHEN condition evaluation over controlled structured state.

WHEN conditions may only reference a whitelisted set of state paths (signal
status/direction, evidence quality, cause presence, step status, coverage) and
a fixed set of operators.  No arbitrary expression, arithmetic on business
values, SQL, eval or Python is permitted.
"""

from app.commerce.diagnostics.plans.schema import WhenCondition

WHEN_EQ = "EQ"
WHEN_IN = "IN"
WHEN_GT = "GT"
WHEN_GTE = "GTE"
WHEN_LT = "LT"
WHEN_LTE = "LTE"
WHEN_EXISTS = "EXISTS"
WHEN_NOT_EXISTS = "NOT_EXISTS"

WHEN_OPERATORS = frozenset({
    WHEN_EQ, WHEN_IN, WHEN_GT, WHEN_GTE, WHEN_LT, WHEN_LTE,
    WHEN_EXISTS, WHEN_NOT_EXISTS,
})

_ALLOWED_PREFIXES = frozenset({
    "signal_status.",
    "signal_direction.",
    "evidence_quality.",
    "has_signal.",
    "has_evidence.",
    "has_cause.",
    "step_status.",
})

_ALLOWED_EXACT = frozenset({"coverage", "data_quality.status"})


def is_allowed_path(path):
    if path in _ALLOWED_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in _ALLOWED_PREFIXES)


def _resolve(path, state):
    if path in _ALLOWED_EXACT:
        if path == "coverage":
            return state.coverage
        if path == "data_quality.status":
            return state.data_quality.status if state.data_quality else None
    if path.startswith("signal_status."):
        return state.signal_status(path[len("signal_status."):])
    if path.startswith("signal_direction."):
        return state.signal_direction(path[len("signal_direction."):])
    if path.startswith("evidence_quality."):
        return state.evidence_quality(path[len("evidence_quality."):])
    if path.startswith("has_signal."):
        return state.has_signal(path[len("has_signal."):])
    if path.startswith("has_evidence."):
        return state.has_evidence(path[len("has_evidence."):])
    if path.startswith("has_cause."):
        return state.has_cause(path[len("has_cause."):])
    if path.startswith("step_status."):
        return state.step_statuses.get(path[len("step_status."):])
    raise ValueError(f"unsupported WHEN path: {path}")


def evaluate_when(condition: WhenCondition, state) -> bool:
    value = _resolve(condition.path, state)
    if condition.operator == WHEN_EXISTS:
        return value is not None and value is not False
    if condition.operator == WHEN_NOT_EXISTS:
        return value is None or value is False
    if condition.operator == WHEN_EQ:
        return value == condition.value
    if condition.operator == WHEN_IN:
        return value in (condition.value or ())
    if condition.operator == WHEN_GT:
        return value is not None and value > condition.value
    if condition.operator == WHEN_GTE:
        return value is not None and value >= condition.value
    if condition.operator == WHEN_LT:
        return value is not None and value < condition.value
    if condition.operator == WHEN_LTE:
        return value is not None and value <= condition.value
    raise ValueError(f"unsupported WHEN operator: {condition.operator}")


def evaluate_all(conditions, state) -> bool:
    return all(evaluate_when(c, state) for c in conditions)


__all__ = [
    "evaluate_when",
    "evaluate_all",
    "is_allowed_path",
    "WHEN_OPERATORS",
    "WHEN_EQ",
    "WHEN_IN",
    "WHEN_GT",
    "WHEN_GTE",
    "WHEN_LT",
    "WHEN_LTE",
    "WHEN_EXISTS",
    "WHEN_NOT_EXISTS",
]
