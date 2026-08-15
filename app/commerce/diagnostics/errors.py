"""Metric diagnostic errors.

All derived-metric failures are typed and fail-closed: a bad definition, a
cyclic dependency graph, a missing dependency value, or a formula problem never
silently produces a wrong number.
"""

from app.commerce.contracts.errors import CommerceError


class MetricError(CommerceError):
    """Base error for the metric infrastructure."""


class MetricDefinitionError(MetricError):
    """A metric definition is structurally invalid."""


class DuplicateMetricDefinitionError(MetricError):
    """A metric was registered more than once (one formula per metric)."""


class UnknownMetricError(MetricError):
    """The requested metric (or a dependency) is not defined."""


class UnknownMetricVersionError(MetricError):
    """The requested metric version does not match the registered version."""


class MissingDependencyError(MetricError):
    """A required dependency value was not supplied at compute time.

    .. deprecated:: Phase 3 hardening
       Missing *runtime business facts* now yield an INSUFFICIENT
       ``MetricResult`` instead of raising.  This error is retained only for
       definition/configuration contexts.
    """


class UnpinnedDependencyError(MetricError):
    """A DERIVED dependency is not pinned to a version (would drift)."""


class CyclicDependencyError(MetricError):
    """The metric dependency graph contains a cycle."""


class MetricEvaluationError(MetricError):
    """Formula parsing or evaluation failed."""


class DivisionByZeroError(MetricEvaluationError):
    """A formula divided by zero (handled by the engine's zero policy)."""


__all__ = [
    "MetricError",
    "MetricDefinitionError",
    "DuplicateMetricDefinitionError",
    "UnknownMetricError",
    "UnknownMetricVersionError",
    "MissingDependencyError",
    "UnpinnedDependencyError",
    "CyclicDependencyError",
    "MetricEvaluationError",
    "DivisionByZeroError",
]
