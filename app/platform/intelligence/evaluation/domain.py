"""Agent evaluation domain (Phase 17.1)."""

from dataclasses import dataclass, field

from app.core.time import utc_now

EVAL_EXECUTION_QUALITY = "execution_quality"
EVAL_BUSINESS_QUALITY = "business_quality"
EVAL_USER_SATISFACTION = "user_satisfaction"
EVAL_SAFETY_QUALITY = "safety_quality"
EVALUATION_TYPES = frozenset({
    EVAL_EXECUTION_QUALITY, EVAL_BUSINESS_QUALITY, EVAL_USER_SATISFACTION,
    EVAL_SAFETY_QUALITY,
})


@dataclass(frozen=True)
class ExecutionSample:
    success: bool = True
    latency_ms: float = 0.0
    cost: float = 0.0


@dataclass(frozen=True)
class AgentEvaluation:
    evaluation_id: str
    agent_id: str
    agent_version: str
    evaluation_type: str
    score: float = 0.0
    execution_id: str = ""
    trace_id: str = ""
    tenant_id: str = ""
    metrics: dict = field(default_factory=dict)
    feedback: float | None = None
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        object.__setattr__(self, "metrics", dict(self.metrics or {}))
        if not self.evaluation_id:
            raise ValueError("evaluation_id is required")
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if self.evaluation_type not in EVALUATION_TYPES:
            raise ValueError(f"unknown evaluation type: {self.evaluation_type}")
        if not (0.0 <= self.score <= 1.0):
            raise ValueError("score must be in [0, 1]")

    def to_dict(self) -> dict:
        return {
            "evaluation_id": self.evaluation_id,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "evaluation_type": self.evaluation_type,
            "score": self.score,
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "metrics": dict(self.metrics),
            "feedback": self.feedback,
            "created_at": self.created_at,
        }


__all__ = [
    "ExecutionSample",
    "AgentEvaluation",
    "EVALUATION_TYPES",
    "EVAL_EXECUTION_QUALITY",
    "EVAL_BUSINESS_QUALITY",
    "EVAL_USER_SATISFACTION",
    "EVAL_SAFETY_QUALITY",
]
