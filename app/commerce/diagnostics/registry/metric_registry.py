"""MetricDefinitionRegistry — the single source of truth for metric formulas.

One metric name maps to exactly one definition (one formula).  Duplicate
registration is rejected, and every definition is structurally validated at
registration time.
"""

from app.commerce.diagnostics.errors import (
    DuplicateMetricDefinitionError,
    MetricDefinitionError,
    MetricEvaluationError,
    UnknownMetricError,
    UnknownMetricVersionError,
)
from app.commerce.diagnostics.kernel.formula import validate_formula
from app.commerce.domain.metrics import (
    METRIC_CLASS_DERIVED,
    METRIC_CLASSES,
    ZERO_POLICIES,
    ZERO_POLICY_NULL,
    ZERO_POLICY_ZERO,
    MetricDefinition,
)


def validate_definition(definition):
    """Structural validation of a metric definition (fail-closed)."""
    if not definition.metric:
        raise MetricDefinitionError("metric name is required")
    if definition.metric_class not in METRIC_CLASSES:
        raise MetricDefinitionError(
            f"unknown metric_class {definition.metric_class!r} for {definition.metric!r}"
        )
    if not definition.version:
        raise MetricDefinitionError(f"metric {definition.metric!r} requires a version")
    if definition.zero_policy not in ZERO_POLICIES:
        raise MetricDefinitionError(
            f"unknown zero_policy {definition.zero_policy!r} for {definition.metric!r}"
        )
    if definition.precision < 0:
        raise MetricDefinitionError(
            f"precision must be >= 0 for {definition.metric!r}"
        )
    if definition.metric_class == METRIC_CLASS_DERIVED:
        if not definition.formula:
            raise MetricDefinitionError(
                f"DERIVED metric {definition.metric!r} requires a formula"
            )
        if not definition.dependencies:
            raise MetricDefinitionError(
                f"DERIVED metric {definition.metric!r} requires dependencies"
            )
        try:
            validate_formula(definition.formula, definition.dependencies)
        except MetricEvaluationError as error:
            raise MetricDefinitionError(
                f"invalid formula for {definition.metric!r}: {error}"
            ) from error
    else:
        if definition.formula or definition.dependencies:
            raise MetricDefinitionError(
                f"SOURCE/AGGREGATED metric {definition.metric!r} must not have "
                "a formula or dependencies"
            )


class MetricDefinitionRegistry:
    """Registers and serves metric definitions keyed by metric name."""

    def __init__(self):
        self._definitions = {}

    def register(self, definition):
        validate_definition(definition)
        if definition.metric in self._definitions:
            raise DuplicateMetricDefinitionError(
                f"metric {definition.metric!r} is already defined"
            )
        self._definitions[definition.metric] = definition
        return definition

    def register_many(self, definitions):
        for definition in definitions:
            self.register(definition)
        return self

    def get(self, metric, version=None):
        definition = self._definitions.get(metric)
        if definition is None:
            raise UnknownMetricError(f"metric {metric!r} is not defined")
        if version is not None and definition.version != version:
            raise UnknownMetricVersionError(
                f"metric {metric!r} has version {definition.version!r}, "
                f"not {version!r}"
            )
        return definition

    def has(self, metric):
        return metric in self._definitions

    def list_definitions(self):
        return sorted(self._definitions.values(), key=lambda d: d.metric)

    def __contains__(self, metric):
        return metric in self._definitions

    def __len__(self):
        return len(self._definitions)


__all__ = [
    "MetricDefinitionRegistry",
    "validate_definition",
    "ZERO_POLICY_NULL",
    "ZERO_POLICY_ZERO",
    "ZERO_POLICIES",
]
