"""Typed results for the metric infrastructure.

``MetricResult`` is the deterministic output of ``MetricEngine``;
``ComparisonResult`` is the deterministic output of ``ComparisonEngine``.
Neither carries anomaly / root-cause / priority interpretation — those belong to
later phases.
"""

from dataclasses import dataclass

METRIC_STATUS_COMPLETE = "COMPLETE"
METRIC_STATUS_INSUFFICIENT = "INSUFFICIENT"
METRIC_STATUS_NULL_RESULT = "NULL_RESULT"
METRIC_STATUSES = frozenset({
    METRIC_STATUS_COMPLETE,
    METRIC_STATUS_INSUFFICIENT,
    METRIC_STATUS_NULL_RESULT,
})


@dataclass(frozen=True)
class MetricResult:
    metric: str
    version: str
    value: float | None
    unit: str
    precision: int
    status: str = METRIC_STATUS_COMPLETE
    dependencies_used: tuple[str, ...] = ()
    zero_policy_applied: bool = False
    missing_dependencies: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "dependencies_used", tuple(self.dependencies_used or ()))
        object.__setattr__(self, "missing_dependencies", tuple(self.missing_dependencies or ()))
        if self.status not in METRIC_STATUSES:
            raise ValueError(f"unknown metric status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "version": self.version,
            "value": self.value,
            "unit": self.unit,
            "precision": self.precision,
            "status": self.status,
            "dependencies_used": list(self.dependencies_used),
            "zero_policy_applied": self.zero_policy_applied,
            "missing_dependencies": list(self.missing_dependencies),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MetricResult":
        return cls(
            metric=data["metric"],
            version=data["version"],
            value=data.get("value"),
            unit=data.get("unit", ""),
            precision=data.get("precision", 4),
            status=data.get("status", METRIC_STATUS_COMPLETE),
            dependencies_used=tuple(data.get("dependencies_used", ())),
            zero_policy_applied=data.get("zero_policy_applied", False),
            missing_dependencies=tuple(data.get("missing_dependencies", ())),
        )


@dataclass(frozen=True)
class ComparisonResult:
    current_value: float | None
    baseline_value: float | None
    absolute_change: float | None
    relative_change: float | None

    def to_dict(self) -> dict:
        return {
            "current_value": self.current_value,
            "baseline_value": self.baseline_value,
            "absolute_change": self.absolute_change,
            "relative_change": self.relative_change,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ComparisonResult":
        return cls(
            current_value=data.get("current_value"),
            baseline_value=data.get("baseline_value"),
            absolute_change=data.get("absolute_change"),
            relative_change=data.get("relative_change"),
        )


# Trend pattern classification (§34)
TREND_SUDDEN = "SUDDEN"
TREND_GRADUAL = "GRADUAL"
TREND_PERSISTENT = "PERSISTENT"
TREND_TRANSIENT = "TRANSIENT"
TREND_STABLE = "STABLE"
TREND_UNKNOWN = "UNKNOWN"
TREND_PATTERNS = frozenset({
    TREND_SUDDEN, TREND_GRADUAL, TREND_PERSISTENT, TREND_TRANSIENT,
    TREND_STABLE, TREND_UNKNOWN,
})


@dataclass(frozen=True)
class TrendResult:
    """Deterministic trend classification of a time series.

    ``pattern`` is one of TREND_*; ``direction`` is UP / DOWN / STABLE / NONE.
    The algorithm and policy versions are recorded for replay.
    """

    pattern: str
    direction: str
    slope: float | None
    algorithm_version: str
    policy_version: str
    sample_size: int

    def to_dict(self) -> dict:
        return {
            "pattern": self.pattern,
            "direction": self.direction,
            "slope": self.slope,
            "algorithm_version": self.algorithm_version,
            "policy_version": self.policy_version,
            "sample_size": self.sample_size,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrendResult":
        return cls(
            pattern=data["pattern"],
            direction=data["direction"],
            slope=data.get("slope"),
            algorithm_version=data.get("algorithm_version", ""),
            policy_version=data.get("policy_version", ""),
            sample_size=data.get("sample_size", 0),
        )


@dataclass(frozen=True)
class ContributionResult:
    """One subject's contribution to a parent change."""

    subject_id: str
    absolute_contribution: float
    relative_contribution: float | None
    rank: int

    def to_dict(self) -> dict:
        return {
            "subject_id": self.subject_id,
            "absolute_contribution": self.absolute_contribution,
            "relative_contribution": self.relative_contribution,
            "rank": self.rank,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContributionResult":
        return cls(
            subject_id=data["subject_id"],
            absolute_contribution=data["absolute_contribution"],
            relative_contribution=data.get("relative_contribution"),
            rank=data.get("rank", 0),
        )


@dataclass(frozen=True)
class ContributionAnalysis:
    """Attribution result: ranked contributions + coverage."""

    items: tuple[ContributionResult, ...] = ()
    coverage: float | None = None
    algorithm_version: str = ""

    def __post_init__(self):
        object.__setattr__(self, "items", tuple(self.items or ()))

    def to_dict(self) -> dict:
        return {
            "items": [item.to_dict() for item in self.items],
            "coverage": self.coverage,
            "algorithm_version": self.algorithm_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContributionAnalysis":
        return cls(
            items=tuple(ContributionResult.from_dict(i) for i in data.get("items", ())),
            coverage=data.get("coverage"),
            algorithm_version=data.get("algorithm_version", ""),
        )


@dataclass(frozen=True)
class PriorityFactors:
    """The five priority inputs (0..1).  Severity is one factor, not priority."""

    severity: float
    business_impact: float
    urgency: float
    confidence: float
    actionability: float

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "business_impact": self.business_impact,
            "urgency": self.urgency,
            "confidence": self.confidence,
            "actionability": self.actionability,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PriorityFactors":
        return cls(
            severity=data["severity"],
            business_impact=data["business_impact"],
            urgency=data["urgency"],
            confidence=data["confidence"],
            actionability=data["actionability"],
        )


__all__ = [
    "MetricResult",
    "ComparisonResult",
    "METRIC_STATUS_COMPLETE",
    "METRIC_STATUS_INSUFFICIENT",
    "METRIC_STATUS_NULL_RESULT",
    "METRIC_STATUSES",
    "TrendResult",
    "ContributionResult",
    "ContributionAnalysis",
    "PriorityFactors",
    "TREND_PATTERNS",
    "TREND_SUDDEN",
    "TREND_GRADUAL",
    "TREND_PERSISTENT",
    "TREND_TRANSIENT",
    "TREND_STABLE",
    "TREND_UNKNOWN",
]
