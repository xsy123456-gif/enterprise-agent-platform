"""MetricRequirementResolver — resolves a metric to its leaf dependencies.

``ROAS -> resolve dependencies -> [AD_SALES, AD_SPEND]``.  DERIVED dependencies
are resolved recursively; the result is the ordered, deduplicated set of
SOURCE / AGGREGATED leaf metrics required to compute the target.  Cycles and
unknown dependencies are rejected (fail-closed).
"""

from app.commerce.diagnostics.errors import CyclicDependencyError
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
        self._resolve(metric, frozenset(), ordered)
        seen = set()
        result = []
        for name in ordered:
            if name not in seen:
                seen.add(name)
                result.append(name)
        return result

    def _resolve(self, metric, stack, ordered):
        definition = self.registry.get(metric)
        if definition.metric_class != METRIC_CLASS_DERIVED:
            ordered.append(metric)
            return
        if metric in stack:
            raise CyclicDependencyError(
                f"cyclic metric dependency detected at {metric!r}"
            )
        for dependency in definition.dependencies:
            self._resolve(dependency, stack | {metric}, ordered)


__all__ = ["MetricRequirementResolver"]
