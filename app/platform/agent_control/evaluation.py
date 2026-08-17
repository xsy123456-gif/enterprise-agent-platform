"""Agent evaluation platform (Phase 13.7).

Production-quality signal for agents: task success, tool efficiency, latency,
cost and user feedback.  Evaluation is recorded per execution; a summary is
aggregated per agent version.
"""

from dataclasses import dataclass, field

from app.core.time import utc_now


@dataclass(frozen=True)
class AgentEvaluation:
    evaluation_id: str
    agent_id: str
    agent_version: str
    task_success: bool = True
    tool_calls: int = 0
    latency_ms: int = 0
    token_cost: float = 0.0
    feedback: float | None = None
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.evaluation_id:
            raise ValueError("evaluation_id is required")
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if self.tool_calls < 0:
            raise ValueError("tool_calls must be >= 0")

    def to_dict(self) -> dict:
        return {
            "evaluation_id": self.evaluation_id,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "task_success": self.task_success,
            "tool_calls": self.tool_calls,
            "latency_ms": self.latency_ms,
            "token_cost": self.token_cost,
            "feedback": self.feedback,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class AgentMetricsSummary:
    agent_id: str
    total_executions: int = 0
    success_rate: float = 0.0
    avg_tool_calls: float = 0.0
    avg_latency_ms: float = 0.0
    total_token_cost: float = 0.0
    avg_feedback: float | None = None

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "total_executions": self.total_executions,
            "success_rate": self.success_rate,
            "avg_tool_calls": self.avg_tool_calls,
            "avg_latency_ms": self.avg_latency_ms,
            "total_token_cost": self.total_token_cost,
            "avg_feedback": self.avg_feedback,
        }


class AgentEvaluationStore:

    def __init__(self):
        self._records = []

    def record(self, evaluation: AgentEvaluation) -> AgentEvaluation:
        self._records.append(evaluation)
        return evaluation

    def list_for(self, agent_id):
        return [e for e in self._records if e.agent_id == agent_id]

    def summary(self, agent_id) -> AgentMetricsSummary:
        records = self.list_for(agent_id)
        if not records:
            return AgentMetricsSummary(agent_id=agent_id)
        total = len(records)
        success = sum(1 for e in records if e.task_success)
        feedbacks = [e.feedback for e in records if e.feedback is not None]
        return AgentMetricsSummary(
            agent_id=agent_id,
            total_executions=total,
            success_rate=success / total,
            avg_tool_calls=sum(e.tool_calls for e in records) / total,
            avg_latency_ms=sum(e.latency_ms for e in records) / total,
            total_token_cost=sum(e.token_cost for e in records),
            avg_feedback=sum(feedbacks) / len(feedbacks) if feedbacks else None,
        )


__all__ = ["AgentEvaluation", "AgentMetricsSummary", "AgentEvaluationStore"]
