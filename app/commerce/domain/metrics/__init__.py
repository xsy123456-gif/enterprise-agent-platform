"""Metrics domain: MetricSeries and MetricDefinition.

All time-series business metrics flow through ``MetricSeries``; dynamic
operational metrics are never inlined into Store / Product / SKU / Campaign /
Review.  ``MetricDefinition`` records the single source of truth for a metric
(especially DERIVED metrics like ROAS / CTR / CVR), so no Skill re-implements
a formula.
"""

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

from app.commerce.domain.base import utc_now

# metric_class values
METRIC_CLASS_SOURCE = "SOURCE"
METRIC_CLASS_AGGREGATED = "AGGREGATED"
METRIC_CLASS_DERIVED = "DERIVED"
METRIC_CLASSES = frozenset({METRIC_CLASS_SOURCE, METRIC_CLASS_AGGREGATED, METRIC_CLASS_DERIVED})

# Zero policies for DERIVED metric formulas.
ZERO_POLICY_NULL = "NULL"
ZERO_POLICY_ZERO = "ZERO"
ZERO_POLICIES = frozenset({ZERO_POLICY_NULL, ZERO_POLICY_ZERO})


def _canonical(value):
    """Recursively sort dict keys so serialization is order-independent."""
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def canonical_dimensions_hash(dimensions) -> str:
    """Deterministic SHA-256 over a canonical (dict-order-independent) JSON
    serialization of ``dimensions``.

    This is the single source of truth for the ``dimensions_hash`` used in the
    MetricSeries natural key, so two records with the same dimensions always
    collapse to the same hash regardless of dictionary insertion order.
    """
    payload = _canonical(dimensions or {})
    serialized = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MetricSeries:
    metric_record_id: str
    tenant_id: str
    subject_type: str
    subject_id: str
    metric_name: str
    metric_class: str
    granularity: str
    period_start: str
    period_end: str
    value: float
    unit: str = ""
    dimensions: dict[str, Any] = field(default_factory=dict)
    dimensions_hash: str = ""
    source_metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        object.__setattr__(self, "dimensions", dict(self.dimensions or {}))
        object.__setattr__(self, "source_metadata", dict(self.source_metadata or {}))

    def to_dict(self) -> dict:
        return {
            "metric_record_id": self.metric_record_id,
            "tenant_id": self.tenant_id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "metric_name": self.metric_name,
            "metric_class": self.metric_class,
            "granularity": self.granularity,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "value": self.value,
            "unit": self.unit,
            "dimensions": dict(self.dimensions),
            "dimensions_hash": self.dimensions_hash,
            "source_metadata": dict(self.source_metadata),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MetricSeries":
        return cls(
            metric_record_id=data["metric_record_id"],
            tenant_id=data["tenant_id"],
            subject_type=data["subject_type"],
            subject_id=data["subject_id"],
            metric_name=data["metric_name"],
            metric_class=data["metric_class"],
            granularity=data["granularity"],
            period_start=data["period_start"],
            period_end=data["period_end"],
            value=data["value"],
            unit=data.get("unit", ""),
            dimensions=data.get("dimensions", {}),
            dimensions_hash=data.get("dimensions_hash", ""),
            source_metadata=data.get("source_metadata", {}),
            updated_at=data.get("updated_at", utc_now()),
        )


@dataclass(frozen=True)
class MetricDefinition:
    """Single source of truth for a metric, especially DERIVED metrics.

    ``dependencies`` name the SOURCE / AGGREGATED metrics required to compute a
    DERIVED metric; ``MetricRequirementResolver`` (Phase 3) walks them so a
    DiagnosticPlan only declares ``ROAS`` without knowing its dependencies.
    """

    metric: str
    metric_class: str
    version: str
    dependencies: tuple[str, ...] = ()
    formula: str = ""
    zero_policy: str = "NULL"
    precision: int = 4
    unit: str = ""

    def __post_init__(self):
        object.__setattr__(self, "dependencies", tuple(self.dependencies or ()))

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "metric_class": self.metric_class,
            "version": self.version,
            "dependencies": list(self.dependencies),
            "formula": self.formula,
            "zero_policy": self.zero_policy,
            "precision": self.precision,
            "unit": self.unit,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MetricDefinition":
        return cls(
            metric=data["metric"],
            metric_class=data["metric_class"],
            version=data["version"],
            dependencies=tuple(data.get("dependencies", ())),
            formula=data.get("formula", ""),
            zero_policy=data.get("zero_policy", "NULL"),
            precision=data.get("precision", 4),
            unit=data.get("unit", ""),
        )


__all__ = [
    "MetricSeries",
    "MetricDefinition",
    "METRIC_CLASS_SOURCE",
    "METRIC_CLASS_AGGREGATED",
    "METRIC_CLASS_DERIVED",
    "METRIC_CLASSES",
    "ZERO_POLICY_NULL",
    "ZERO_POLICY_ZERO",
    "ZERO_POLICIES",
    "canonical_dimensions_hash",
]
