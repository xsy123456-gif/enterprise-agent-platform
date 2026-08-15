"""Typed results for the metric infrastructure.

``MetricResult`` is the deterministic output of ``MetricEngine``;
``ComparisonResult`` is the deterministic output of ``ComparisonEngine``.
Neither carries anomaly / root-cause / priority interpretation — those belong to
later phases.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricResult:
    metric: str
    version: str
    value: float | None
    unit: str
    precision: int
    dependencies_used: tuple[str, ...] = ()
    zero_policy_applied: bool = False
    missing_dependencies: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "dependencies_used", tuple(self.dependencies_used or ()))
        object.__setattr__(self, "missing_dependencies", tuple(self.missing_dependencies or ()))

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "version": self.version,
            "value": self.value,
            "unit": self.unit,
            "precision": self.precision,
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


__all__ = ["MetricResult", "ComparisonResult"]
