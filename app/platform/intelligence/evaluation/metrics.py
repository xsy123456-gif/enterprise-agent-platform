"""Evaluation metrics (Phase 17.1)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvaluationMetrics:
    success_rate: float = 0.0
    failure_rate: float = 0.0
    avg_latency_ms: float = 0.0
    avg_cost: float = 0.0
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "extra", dict(self.extra or {}))

    def to_dict(self) -> dict:
        return {
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "avg_cost": self.avg_cost,
            **self.extra,
        }


__all__ = ["EvaluationMetrics"]
