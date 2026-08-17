"""MetricEngine — computes DERIVED metrics deterministically.

Every DERIVED metric is computed through its single ``MetricDefinition``:
dependencies are resolved (recursively for nested DERIVED metrics, using their
pinned versions), the declarative formula is evaluated by the safe parser, the
zero policy is applied on division by zero, and the result is rounded to the
definition precision.  Same inputs + same definition version always produce the
same result.

Runtime missing business facts do NOT raise: they produce an INSUFFICIENT
``MetricResult`` (``value=None`` + ``missing_dependencies``).  Only definition /
configuration / programming errors raise.
"""

from app.commerce.diagnostics.errors import (
    DivisionByZeroError,
    MetricDefinitionError,
)
from app.commerce.diagnostics.kernel.formula import evaluate_expression
from app.commerce.diagnostics.models import (
    METRIC_STATUS_COMPLETE,
    METRIC_STATUS_INSUFFICIENT,
    METRIC_STATUS_NULL_RESULT,
    MetricResult,
)
from app.commerce.diagnostics.registry.resolver import MetricRequirementResolver
from app.commerce.domain.metrics import METRIC_CLASS_DERIVED, ZERO_POLICY_ZERO


class MetricEngine:

    def __init__(self, registry, resolver=None):
        self.registry = registry
        self.resolver = resolver or MetricRequirementResolver(registry)

    def compute(self, metric, values, version=None):
        """Compute ``metric`` from a ``values`` mapping of leaf metric -> number.

        ``values`` maps SOURCE / AGGREGATED metric names to their numeric value
        (or ``None``).  Returns a ``MetricResult``.
        """
        definition = self.registry.get(metric, version)
        if definition.metric_class != METRIC_CLASS_DERIVED:
            raise MetricDefinitionError(
                f"metric {metric!r} is not DERIVED; MetricEngine only computes "
                "derived metrics"
            )
        leaf_dependencies = self.resolver.resolve(metric, definition.version)
        dependency_values = {}
        for dependency in definition.dependencies:
            dependency_version = definition.dependency_versions.get(dependency)
            dependency_values[dependency] = self._value_of(
                dependency, values, dependency_version
            )
        missing = tuple(
            name for name, value in dependency_values.items() if value is None
        )
        if missing:
            return self._result(
                definition, leaf_dependencies, value=None,
                status=METRIC_STATUS_INSUFFICIENT, missing_dependencies=missing,
            )
        try:
            raw, _used = evaluate_expression(definition.formula, dependency_values)
        except DivisionByZeroError:
            value = 0.0 if definition.zero_policy == ZERO_POLICY_ZERO else None
            status = (
                METRIC_STATUS_COMPLETE if value is not None
                else METRIC_STATUS_NULL_RESULT
            )
            return self._result(
                definition, leaf_dependencies, value=value, status=status,
                zero_policy_applied=True,
            )
        return self._result(
            definition, leaf_dependencies, value=raw,
            status=METRIC_STATUS_COMPLETE,
        )

    def _value_of(self, dependency, values, version):
        if dependency in values:
            return values[dependency]
        definition = self.registry.get(dependency, version)
        if definition.metric_class == METRIC_CLASS_DERIVED:
            return self.compute(dependency, values, version).value
        # SOURCE/AGGREGATED fact absent at runtime -> INSUFFICIENT (not an error).
        return None

    @staticmethod
    def _result(definition, leaf_dependencies, value=None, status=METRIC_STATUS_COMPLETE,
                zero_policy_applied=False, missing_dependencies=()):
        rounded = None if value is None else round(float(value), definition.precision)
        return MetricResult(
            metric=definition.metric,
            version=definition.version,
            value=rounded,
            unit=definition.unit,
            precision=definition.precision,
            status=status,
            dependencies_used=tuple(leaf_dependencies),
            zero_policy_applied=zero_policy_applied,
            missing_dependencies=tuple(missing_dependencies),
        )


__all__ = ["MetricEngine"]
