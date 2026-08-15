"""MetricEngine — computes DERIVED metrics deterministically.

Every DERIVED metric is computed through its single ``MetricDefinition``:
dependencies are resolved (recursively for nested DERIVED metrics), the
declarative formula is evaluated by the safe parser, the zero policy is applied
on division by zero, and the result is rounded to the definition precision.
Same inputs + same definition version always produce the same result.
"""

from app.commerce.diagnostics.errors import (
    DivisionByZeroError,
    MetricDefinitionError,
    MissingDependencyError,
)
from app.commerce.diagnostics.kernel.formula import evaluate_expression
from app.commerce.diagnostics.models import MetricResult
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
        dependency_values = {
            dependency: self._value_of(dependency, values)
            for dependency in definition.dependencies
        }
        missing = tuple(
            name for name, value in dependency_values.items() if value is None
        )
        if missing:
            return self._result(definition, leaf_dependencies, value=None,
                                missing_dependencies=missing)
        try:
            raw, _used = evaluate_expression(definition.formula, dependency_values)
        except DivisionByZeroError:
            value = 0.0 if definition.zero_policy == ZERO_POLICY_ZERO else None
            return self._result(definition, leaf_dependencies, value=value,
                                zero_policy_applied=True)
        return self._result(definition, leaf_dependencies, value=raw)

    def _value_of(self, dependency, values):
        if dependency in values:
            return values[dependency]
        definition = self.registry.get(dependency)
        if definition.metric_class == METRIC_CLASS_DERIVED:
            return self.compute(dependency, values).value
        raise MissingDependencyError(
            f"missing dependency value for {dependency!r}"
        )

    @staticmethod
    def _result(definition, leaf_dependencies, value=None, zero_policy_applied=False,
                missing_dependencies=()):
        rounded = None if value is None else round(float(value), definition.precision)
        return MetricResult(
            metric=definition.metric,
            version=definition.version,
            value=rounded,
            unit=definition.unit,
            precision=definition.precision,
            dependencies_used=tuple(leaf_dependencies),
            zero_policy_applied=zero_policy_applied,
            missing_dependencies=tuple(missing_dependencies),
        )


__all__ = ["MetricEngine"]
