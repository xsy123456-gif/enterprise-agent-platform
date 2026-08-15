"""Metric diagnostic infrastructure (Phase 3).

Deterministic computation of DERIVED metrics from a single source of truth
(MetricDefinitionRegistry + MetricEngine) and current-vs-baseline comparison
(ComparisonEngine).  This phase does NOT implement trend / anomaly /
contribution / rule / impact / priority engines.
"""

from app.commerce.diagnostics.definitions.metrics import (
    build_core_metric_definitions,
    build_core_metric_registry,
)
from app.commerce.diagnostics.kernel.comparison_engine import ComparisonEngine
from app.commerce.diagnostics.kernel.metric_engine import MetricEngine
from app.commerce.diagnostics.models import ComparisonResult, MetricResult
from app.commerce.diagnostics.registry.metric_registry import (
    MetricDefinitionRegistry,
)
from app.commerce.diagnostics.registry.resolver import MetricRequirementResolver

__all__ = [
    "MetricEngine",
    "ComparisonEngine",
    "MetricResult",
    "ComparisonResult",
    "MetricDefinitionRegistry",
    "MetricRequirementResolver",
    "build_core_metric_definitions",
    "build_core_metric_registry",
]
