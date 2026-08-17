"""Evaluation engine (Phase 17.1).

Computes a quality ``AgentEvaluation`` from execution samples — data-driven
only, never an LLM opinion.
"""

from app.platform.intelligence.evaluation.domain import (
    EVAL_EXECUTION_QUALITY,
    AgentEvaluation,
    ExecutionSample,
)
from app.platform.intelligence.evaluation.metrics import EvaluationMetrics


class EvaluationEngine:

    def evaluate_execution_quality(self, evaluation_id, agent_id, agent_version,
                                   samples, execution_id="") -> AgentEvaluation:
        total = len(samples)
        if total == 0:
            metrics = EvaluationMetrics()
            score = 0.0
        else:
            success = sum(1 for s in samples if s.success)
            metrics = EvaluationMetrics(
                success_rate=success / total,
                failure_rate=(total - success) / total,
                avg_latency_ms=sum(s.latency_ms for s in samples) / total,
                avg_cost=sum(s.cost for s in samples) / total,
            )
            score = metrics.success_rate
        return AgentEvaluation(
            evaluation_id=evaluation_id, agent_id=agent_id,
            agent_version=agent_version,
            evaluation_type=EVAL_EXECUTION_QUALITY, score=score,
            execution_id=execution_id, metrics=metrics.to_dict(),
        )

    def evaluate_execution(self, evaluation_id, agent_id, agent_version, sample,
                           execution_id="", trace_id="", tenant_id="") -> AgentEvaluation:
        """Evaluate a *single* execution (success/failure/latency/cost).

        The score is the execution outcome (1.0 success / 0.0 failure), NOT a
        success_rate — avoiding the semantic error of calling one sample
        "100% success rate".
        """
        score = 1.0 if sample.success else 0.0
        return AgentEvaluation(
            evaluation_id=evaluation_id, agent_id=agent_id,
            agent_version=agent_version,
            evaluation_type=EVAL_EXECUTION_QUALITY, score=score,
            execution_id=execution_id, trace_id=trace_id, tenant_id=tenant_id,
            metrics={
                "success": sample.success,
                "latency_ms": sample.latency_ms,
                "cost": sample.cost,
            },
        )


__all__ = ["EvaluationEngine"]
