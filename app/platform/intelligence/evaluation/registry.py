"""Evaluation metric model + registry (Phase 17.1)."""

from dataclasses import dataclass

from app.commerce.diagnostics.registry.base import VersionedRegistry


@dataclass(frozen=True)
class EvaluationMetric:
    metric_id: str
    name: str
    category: str
    formula: str
    version: str = "1.0"
    threshold: float = 0.0

    def __post_init__(self):
        if not self.metric_id:
            raise ValueError("metric_id is required")

    def to_dict(self) -> dict:
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "category": self.category,
            "formula": self.formula,
            "version": self.version,
            "threshold": self.threshold,
        }


class EvaluationMetricRegistry(VersionedRegistry):

    def __init__(self):
        super().__init__("evaluation metric")

    def register(self, metric: EvaluationMetric):
        return super().register(metric.metric_id, metric.version, metric)

    def get(self, metric_id, version=None):
        return super().get(metric_id, version)


__all__ = ["EvaluationMetric", "EvaluationMetricRegistry"]
