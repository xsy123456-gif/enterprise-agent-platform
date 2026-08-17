"""Collaboration evaluation (Phase 14.7).

Collaboration-level quality metrics: collaboration success, delegation
efficiency, agent overuse, context efficiency and cost efficiency.
"""

from dataclasses import dataclass, field

from app.core.time import utc_now


@dataclass(frozen=True)
class CollaborationEvaluation:
    evaluation_id: str
    task_id: str
    collaboration_success: bool = True
    delegation_efficiency: float = 0.0
    agent_overuse_rate: float = 0.0
    context_efficiency: float = 0.0
    cost_efficiency: float = 0.0
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.evaluation_id:
            raise ValueError("evaluation_id is required")
        for name in ("delegation_efficiency", "agent_overuse_rate",
                     "context_efficiency", "cost_efficiency"):
            value = getattr(self, name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be in [0, 1]")

    def to_dict(self) -> dict:
        return {
            "evaluation_id": self.evaluation_id,
            "task_id": self.task_id,
            "collaboration_success": self.collaboration_success,
            "delegation_efficiency": self.delegation_efficiency,
            "agent_overuse_rate": self.agent_overuse_rate,
            "context_efficiency": self.context_efficiency,
            "cost_efficiency": self.cost_efficiency,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class CollaborationSummary:
    total_tasks: int = 0
    success_rate: float = 0.0
    avg_delegation_efficiency: float = 0.0
    avg_agent_overuse_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_tasks": self.total_tasks,
            "success_rate": self.success_rate,
            "avg_delegation_efficiency": self.avg_delegation_efficiency,
            "avg_agent_overuse_rate": self.avg_agent_overuse_rate,
        }


class CollaborationEvaluationStore:

    def __init__(self):
        self._records = []

    def record(self, evaluation: CollaborationEvaluation):
        self._records.append(evaluation)
        return evaluation

    def list(self):
        return list(self._records)

    def summary(self) -> CollaborationSummary:
        if not self._records:
            return CollaborationSummary()
        total = len(self._records)
        success = sum(1 for e in self._records if e.collaboration_success)
        return CollaborationSummary(
            total_tasks=total,
            success_rate=success / total,
            avg_delegation_efficiency=sum(
                e.delegation_efficiency for e in self._records) / total,
            avg_agent_overuse_rate=sum(
                e.agent_overuse_rate for e in self._records) / total,
        )


__all__ = [
    "CollaborationEvaluation",
    "CollaborationSummary",
    "CollaborationEvaluationStore",
]
