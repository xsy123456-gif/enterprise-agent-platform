"""DiagnosticPolicy — versioned anomaly/trend detection thresholds.

Engines never hard-code thresholds; every detection threshold, sample-sufficiency
floor and z-score bound comes from a versioned ``DiagnosticPolicy``.  This is
the business-knowledge boundary the kernel engines consume.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiagnosticPolicy:
    policy_id: str
    version: str
    domain: str = ""
    # Anomaly detection (§35)
    min_sample_size: int = 0
    min_baseline_volume: float = 0.0
    warning_relative_change: float = 0.10
    abnormal_relative_change: float = 0.20
    critical_relative_change: float = 0.40
    warning_zscore: float = 1.5
    abnormal_zscore: float = 2.0
    critical_zscore: float = 3.0
    # Trend detection (§34)
    trend_min_points: int = 3
    baseline_window: int = 7
    recent_window: int = 3
    stability_threshold: float = 0.05
    sudden_threshold: float = 0.25
    persistence_periods: int = 3
    # Applicability: empty tuple = applies to all subject types.
    applicable_subject_types: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(
            self, "applicable_subject_types", tuple(self.applicable_subject_types or ())
        )

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "domain": self.domain,
            "min_sample_size": self.min_sample_size,
            "min_baseline_volume": self.min_baseline_volume,
            "warning_relative_change": self.warning_relative_change,
            "abnormal_relative_change": self.abnormal_relative_change,
            "critical_relative_change": self.critical_relative_change,
            "warning_zscore": self.warning_zscore,
            "abnormal_zscore": self.abnormal_zscore,
            "critical_zscore": self.critical_zscore,
            "trend_min_points": self.trend_min_points,
            "baseline_window": self.baseline_window,
            "recent_window": self.recent_window,
            "stability_threshold": self.stability_threshold,
            "sudden_threshold": self.sudden_threshold,
            "persistence_periods": self.persistence_periods,
            "applicable_subject_types": list(self.applicable_subject_types),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiagnosticPolicy":
        return cls(
            policy_id=data["policy_id"],
            version=data["version"],
            domain=data.get("domain", ""),
            min_sample_size=data.get("min_sample_size", 0),
            min_baseline_volume=data.get("min_baseline_volume", 0.0),
            warning_relative_change=data.get("warning_relative_change", 0.10),
            abnormal_relative_change=data.get("abnormal_relative_change", 0.20),
            critical_relative_change=data.get("critical_relative_change", 0.40),
            warning_zscore=data.get("warning_zscore", 1.5),
            abnormal_zscore=data.get("abnormal_zscore", 2.0),
            critical_zscore=data.get("critical_zscore", 3.0),
            trend_min_points=data.get("trend_min_points", 3),
            baseline_window=data.get("baseline_window", 7),
            recent_window=data.get("recent_window", 3),
            stability_threshold=data.get("stability_threshold", 0.05),
            sudden_threshold=data.get("sudden_threshold", 0.25),
            persistence_periods=data.get("persistence_periods", 3),
            applicable_subject_types=tuple(data.get("applicable_subject_types", ())),
        )


def build_default_diagnostic_policies():
    """A minimal default policy set (one per commerce domain)."""
    return [
        DiagnosticPolicy(policy_id="commerce.standard.v1", version="1.0", domain="*"),
    ]


__all__ = ["DiagnosticPolicy", "build_default_diagnostic_policies"]
