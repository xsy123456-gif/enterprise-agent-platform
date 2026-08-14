"""Condition AST — declarative, side-effect-free policy conditions.

Condition nodes form a tree: atomic comparisons plus ``all`` / ``any`` /
``not`` combinators.  No dynamic code, no eval, no I/O.
"""

from dataclasses import dataclass, field
from typing import Any, Union


@dataclass(frozen=True)
class AtomicCondition:
    field: str
    operator: str
    value: Any = None
    value_from: str | None = None
    dimension: str | None = None


@dataclass(frozen=True)
class AllCondition:
    conditions: tuple["ConditionNode", ...]


@dataclass(frozen=True)
class AnyCondition:
    conditions: tuple["ConditionNode", ...]


@dataclass(frozen=True)
class NotCondition:
    condition: "ConditionNode"


ConditionNode = Union[AtomicCondition, AllCondition, AnyCondition, NotCondition]
