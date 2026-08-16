"""Shared evaluation helpers (Phase 18.15)."""

from tools.benchmark.models import (
    VERDICT_FAIL,
    VERDICT_NOT_APPLICABLE,
    VERDICT_PASS,
    EvaluationResult,
)


def result(layer, passed, assertions):
    verdict = VERDICT_PASS if passed else VERDICT_FAIL
    return EvaluationResult(layer, verdict, tuple(assertions))


def not_applicable(layer):
    return EvaluationResult(layer, VERDICT_NOT_APPLICABLE, ())


def assertion(name, expected, actual, passed=None):
    if passed is None:
        passed = (expected == actual)
    return {"name": name, "expected": expected, "actual": actual,
            "passed": bool(passed)}


__all__ = ["result", "not_applicable", "assertion"]
