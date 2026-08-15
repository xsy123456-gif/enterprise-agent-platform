"""Safe formula evaluator tests (no eval/exec)."""

import pytest

from app.commerce.diagnostics.errors import (
    DivisionByZeroError,
    MetricEvaluationError,
)
from app.commerce.diagnostics.kernel.formula import (
    evaluate_expression,
    validate_formula,
)


def test_simple_division():
    value, used = evaluate_expression("AD_SALES / AD_SPEND",
                                      {"AD_SALES": 100.0, "AD_SPEND": 50.0})
    assert value == 2.0
    assert used == frozenset({"AD_SALES", "AD_SPEND"})


def test_precedence_and_parentheses():
    value, _ = evaluate_expression("(A + B) * C", {"A": 1.0, "B": 2.0, "C": 3.0})
    assert value == 9.0
    value, _ = evaluate_expression("A + B * C", {"A": 1.0, "B": 2.0, "C": 3.0})
    assert value == 7.0


def test_numeric_literals():
    value, _ = evaluate_expression("A * 100", {"A": 0.05})
    assert value == pytest.approx(5.0)


def test_division_by_zero_raises():
    with pytest.raises(DivisionByZeroError):
        evaluate_expression("A / B", {"A": 1.0, "B": 0.0})


def test_undeclared_identifier_raises():
    with pytest.raises(MetricEvaluationError):
        evaluate_expression("A / B", {"A": 1.0})


def test_none_value_raises():
    with pytest.raises(MetricEvaluationError):
        evaluate_expression("A / B", {"A": 1.0, "B": None})


def test_syntax_error_raises():
    with pytest.raises(MetricEvaluationError):
        evaluate_expression("A /", {"A": 1.0})


def test_no_code_execution():
    # Only numbers, identifiers and + - * / ( ) are allowed; anything else is
    # rejected by the tokenizer rather than evaluated.
    for malicious in [
        "__import__('os')",
        "A; os.system('x')",
        "A.__class__",
        "A[0]",
        "1 if True else 0",
        "open('x')",
    ]:
        with pytest.raises(MetricEvaluationError):
            evaluate_expression(malicious, {"A": 1.0})


def test_validate_formula_returns_used():
    used = validate_formula("AD_SALES / AD_SPEND", ("AD_SALES", "AD_SPEND"))
    assert used == frozenset({"AD_SALES", "AD_SPEND"})


def test_validate_formula_rejects_undeclared():
    with pytest.raises(MetricEvaluationError):
        validate_formula("AD_SALES / OTHER", ("AD_SALES", "AD_SPEND"))
