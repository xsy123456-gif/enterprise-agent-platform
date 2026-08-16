"""Agent metrics collector (Phase 15.1).

Reliability / performance / cost / quality signals, aggregated per agent.  SLA
(availability / latency / success rate) is derived from the same samples.
"""

from dataclasses import dataclass, field

from app.core.time import utc_now


@dataclass(frozen=True)
class AgentMetricSample:
    tenant_id: str
    agent_id: str
    success: bool = True
    latency_ms: float = 0.0
    retry_count: int = 0
    token_usage: int = 0
    tool_cost: float = 0.0
    execution_cost: float = 0.0
    feedback: float | None = None
    at: str = field(default_factory=utc_now)
    execution_id: str = ""
    trace_id: str = ""
    agent_version: str = ""

    def __post_init__(self):
        if self.retry_count < 0:
            raise ValueError("retry_count must be >= 0")


@dataclass(frozen=True)
class AgentMetricsSummary:
    agent_id: str
    total: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    avg_latency_ms: float = 0.0
    total_retry_count: int = 0
    total_token_usage: int = 0
    total_cost: float = 0.0
    avg_feedback: float | None = None

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "total": self.total,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "total_retry_count": self.total_retry_count,
            "total_token_usage": self.total_token_usage,
            "total_cost": self.total_cost,
            "avg_feedback": self.avg_feedback,
        }


@dataclass(frozen=True)
class AgentSLA:
    agent_id: str
    availability: float = 0.0
    latency_p95: float = 0.0
    success_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "availability": self.availability,
            "latency_p95": self.latency_p95,
            "success_rate": self.success_rate,
        }


class AgentMetricsCollector:

    def __init__(self):
        self._samples = {}

    def record(self, sample: AgentMetricSample):
        self._samples.setdefault(sample.agent_id, []).append(sample)
        return sample

    def samples(self, agent_id):
        return tuple(self._samples.get(agent_id, ()))

    def summary(self, agent_id) -> AgentMetricsSummary:
        samples = self._samples.get(agent_id, [])
        if not samples:
            return AgentMetricsSummary(agent_id=agent_id)
        total = len(samples)
        success = sum(1 for s in samples if s.success)
        feedbacks = [s.feedback for s in samples if s.feedback is not None]
        return AgentMetricsSummary(
            agent_id=agent_id,
            total=total,
            success_rate=success / total,
            failure_rate=(total - success) / total,
            avg_latency_ms=sum(s.latency_ms for s in samples) / total,
            total_retry_count=sum(s.retry_count for s in samples),
            total_token_usage=sum(s.token_usage for s in samples),
            total_cost=sum(s.tool_cost + s.execution_cost for s in samples),
            avg_feedback=sum(feedbacks) / len(feedbacks) if feedbacks else None,
        )

    def sla(self, agent_id) -> AgentSLA:
        summary = self.summary(agent_id)
        latencies = sorted(s.latency_ms for s in self._samples.get(agent_id, ()))
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
        return AgentSLA(
            agent_id=agent_id,
            availability=1.0 - summary.failure_rate,
            latency_p95=p95,
            success_rate=summary.success_rate,
        )


__all__ = [
    "AgentMetricSample",
    "AgentMetricsSummary",
    "AgentSLA",
    "AgentMetricsCollector",
]
