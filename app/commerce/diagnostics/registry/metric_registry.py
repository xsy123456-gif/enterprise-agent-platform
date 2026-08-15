"""MetricDefinitionRegistry — the single source of truth for metric formulas.

Definition identity is ``(metric_name, version)``: multiple versions of the
same metric may coexist, while registering the same ``(name, version)`` twice
fails closed.  Each metric has an explicit *active* version used when no
version is requested; registering a later version never silently changes the
active version.
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
    pinned = set(definition.dependency_versions)
    unknown_pins = pinned - set(definition.dependencies)
    if unknown_pins:
        raise MetricDefinitionError(
            f"metric {definition.metric!r} pins undeclared dependencies: "
            f"{sorted(unknown_pins)}"
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
    """Registers and serves metric definitions keyed by ``(name, version)``."""

    def __init__(self):
        self._definitions = {}
        self._active = {}

    def register(self, definition):
        validate_definition(definition)
        key = (definition.metric, definition.version)
        if key in self._definitions:
            raise DuplicateMetricDefinitionError(
                f"metric {definition.metric!r} version {definition.version!r} "
                "is already defined"
            )
        self._definitions[key] = definition
        # First version becomes active; later versions never auto-activate.
        if definition.metric not in self._active:
            self._active[definition.metric] = definition.version
        return definition

    def register_many(self, definitions):
        for definition in definitions:
            self.register(definition)
        return self

    def get(self, metric, version=None):
        """Return the requested version, or the active version when ``None``."""
        if version is None:
            active = self._active.get(metric)
            if active is None:
                raise UnknownMetricError(f"metric {metric!r} is not defined")
            return self._definitions[(metric, active)]
        definition = self._definitions.get((metric, version))
        if definition is None:
            if metric not in self._active:
                raise UnknownMetricError(f"metric {metric!r} is not defined")
            raise UnknownMetricVersionError(
                f"metric {metric!r} has no version {version!r}"
            )
        return definition

    def activate(self, metric, version):
        """Explicitly promote ``version`` to the active version of ``metric``."""
        definition = self._definitions.get((metric, version))
        if definition is None:
            raise UnknownMetricVersionError(
                f"metric {metric!r} has no version {version!r}"
            )
        self._active[metric] = version
        return definition

    def active_version(self, metric):
        return self._active.get(metric)

    def versions(self, metric):
        return sorted(
            version for (name, version) in self._definitions if name == metric
        )

    def has(self, metric):
        return metric in self._active

    def list_definitions(self):
        return sorted(self._definitions.values(), key=lambda d: (d.metric, d.version))

    def __contains__(self, metric):
        return metric in self._active

    def __len__(self):
        return len(self._definitions)


__all__ = [
    "MetricDefinitionRegistry",
    "validate_definition",
    "ZERO_POLICY_NULL",
    "ZERO_POLICY_ZERO",
    "ZERO_POLICIES",
]
