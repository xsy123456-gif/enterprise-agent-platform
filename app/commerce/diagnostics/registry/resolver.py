"""MetricRequirementResolver — resolves a metric to its leaf dependencies.

``ROAS -> resolve dependencies -> [AD_SALES, AD_SPEND]``.  DERIVED dependencies
are resolved recursively; the result is the ordered, deduplicated set of
SOURCE / AGGREGATED leaf metrics required to compute the target.

Version determinism: a DERIVED dependency must be version-pinned (via
``dependency_versions``) so replaying a historical definition never drifts to
the latest version.  Cycles and unknown dependencies are rejected (fail-closed).
"""

from app.commerce.diagnostics.errors import (
    CyclicDependencyError,
    UnpinnedDependencyError,
)
from app.commerce.domain.metrics import METRIC_CLASS_DERIVED


class MetricRequirementResolver:

    def __init__(self, registry):
        self.registry = registry

    def resolve(self, metric, version=None):
        """Return the ordered leaf (SOURCE/AGGREGATED) dependency names."""
        definition = self.registry.get(metric, version)
        if definition.metric_class != METRIC_CLASS_DERIVED:
            return [metric]
        ordered = []
        self._resolve_def(metric, definition.version, frozenset(), ordered)
        seen = set()
        result = []
        for name in ordered:
            if name not in seen:
                seen.add(name)
                result.append(name)
        return result

    def _resolve_def(self, metric, version, stack, ordered):
        definition = self.registry.get(metric, version)
        if definition.metric_class != METRIC_CLASS_DERIVED:
            ordered.append(metric)
            return
        identity = (metric, definition.version)
        if identity in stack:
            raise CyclicDependencyError(
                f"cyclic metric dependency detected at "
                f"{metric}@{definition.version}"
            )
        for dependency in definition.dependencies:
            dependency_version = definition.dependency_versions.get(dependency)
            if dependency_version is None:
                dependency_definition = self.registry.get(dependency)
                if dependency_definition.metric_class == METRIC_CLASS_DERIVED:
                    raise UnpinnedDependencyError(
                        f"DERIVED dependency {dependency!r} of "
                        f"{metric}@{definition.version} must be version-pinned"
                    )
            self._resolve_def(
                dependency, dependency_version, stack | {identity}, ordered
            )


__all__ = ["MetricRequirementResolver"]
