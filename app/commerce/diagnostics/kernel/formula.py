"""Safe arithmetic formula evaluation.

Derived-metric formulas are declarative strings such as ``AD_SALES / AD_SPEND``.
They are parsed and evaluated by a small recursive-descent parser here — never
with ``eval`` / ``exec`` — and identifiers are restricted to the metric's
declared dependencies.
"""

import re

from app.commerce.diagnostics.errors import DivisionByZeroError, MetricEvaluationError

_TOKEN = re.compile(
    r"\s*(?:(?P<number>\d+(?:\.\d+)?)|(?P<ident>[A-Za-z_][A-Za-z0-9_]*)|(?P<op>[+\-*/()]))"
)

_ADD_OPS = {"+", "-"}
_MUL_OPS = {"*", "/"}


def tokenize(expression):
    tokens = []
    pos = 0
    length = len(expression)
    while pos < length:
        match = _TOKEN.match(expression, pos)
        if match is None or match.end() == pos:
            raise MetricEvaluationError(
                f"unexpected character in formula: {expression[pos:]!r}"
            )
        pos = match.end()
        if match.group("number") is not None:
            tokens.append(("number", float(match.group("number"))))
        elif match.group("ident") is not None:
            tokens.append(("ident", match.group("ident")))
        else:
            tokens.append(("op", match.group("op")))
    tokens.append(("end", None))
    return tokens


class _Parser:
    def __init__(self, tokens, variables):
        self.tokens = tokens
        self.pos = 0
        self.variables = variables
        self.used = set()

    def _peek(self):
        return self.tokens[self.pos]

    def _advance(self):
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def parse(self):
        value = self._expr()
        if self._peek()[0] != "end":
            raise MetricEvaluationError("unexpected trailing tokens in formula")
        return value

    def _expr(self):
        value = self._term()
        while self._peek()[0] == "op" and self._peek()[1] in _ADD_OPS:
            op = self._advance()[1]
            rhs = self._term()
            value = value + rhs if op == "+" else value - rhs
        return value

    def _term(self):
        value = self._factor()
        while self._peek()[0] == "op" and self._peek()[1] in _MUL_OPS:
            op = self._advance()[1]
            rhs = self._factor()
            if op == "*":
                value = value * rhs
            else:
                if rhs == 0:
                    raise DivisionByZeroError("division by zero in formula")
                value = value / rhs
        return value

    def _factor(self):
        kind, value = self._peek()
        if kind == "number":
            self._advance()
            return value
        if kind == "ident":
            self._advance()
            if value not in self.variables:
                raise MetricEvaluationError(
                    f"undeclared identifier {value!r} in formula"
                )
            self.used.add(value)
            variable = self.variables[value]
            if variable is None:
                raise MetricEvaluationError(f"identifier {value!r} has no value")
            return variable
        if kind == "op" and value == "(":
            self._advance()
            result = self._expr()
            if self._peek() != ("op", ")"):
                raise MetricEvaluationError("expected ')' in formula")
            self._advance()
            return result
        raise MetricEvaluationError("unexpected token in formula")


def evaluate_expression(expression, variables):
    """Evaluate ``expression`` against ``variables`` (name -> float).

    Returns ``(value, used_identifiers)``.  Raises ``DivisionByZeroError`` on a
    zero denominator and ``MetricEvaluationError`` on syntax errors or
    undeclared identifiers.
    """
    tokens = tokenize(expression)
    parser = _Parser(tokens, dict(variables or {}))
    return parser.parse(), frozenset(parser.used)


def validate_formula(expression, dependencies):
    """Validate a formula against its declared dependencies.

    Returns the set of identifiers actually used.  Raises
    ``MetricEvaluationError`` on syntax errors or any identifier not present in
    ``dependencies``.
    """
    _, used = evaluate_expression(expression, {dep: 1.0 for dep in dependencies})
    return used


__all__ = ["evaluate_expression", "validate_formula", "tokenize"]
