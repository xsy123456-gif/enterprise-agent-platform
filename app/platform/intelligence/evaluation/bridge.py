"""Production -> Intelligence Evaluation bridge (Phase 18.9).

``EvaluationSubscriber`` consumes a production ``AgentMetricSample`` (the output
of Production Observability) and maps it into a single-execution
``AgentEvaluation`` via the existing ``EvaluationEngine``.  It never re-executes
an agent, never computes a diagnostic cause, never calls a tool, and never
changes the already-completed business result — evaluation is a post-hoc
consumer, so an evaluation failure is isolated and visible but does not change
the execution outcome.
"""

import uuid

from app.platform.intelligence.evaluation.domain import ExecutionSample
from app.platform.intelligence.evaluation.evaluator import EvaluationEngine
from app.platform.intelligence.evaluation.store import (
    EvaluationStore,
    InMemoryEvaluationStore,
)


class EvaluationSubscriber:

    def __init__(self, evaluation_engine=None, evaluation_store=None):
        self.evaluation_engine = evaluation_engine or EvaluationEngine()
        self.evaluation_store = evaluation_store or InMemoryEvaluationStore()
        self.errors = []

    def on_metric_sample(self, sample):
        """Map a production metric sample into a single-execution evaluation."""
        try:
            evaluation = self.evaluation_engine.evaluate_execution(
                evaluation_id=uuid.uuid4().hex,
                agent_id=sample.agent_id,
                agent_version=getattr(sample, "agent_version", ""),
                sample=ExecutionSample(
                    success=sample.success,
                    latency_ms=sample.latency_ms,
                    cost=getattr(sample, "tool_cost", 0.0)
                    + getattr(sample, "execution_cost", 0.0),
                ),
                execution_id=sample.execution_id,
                trace_id=getattr(sample, "trace_id", ""),
                tenant_id=sample.tenant_id,
            )
            self.evaluation_store.put(evaluation)
            return evaluation
        except Exception as error:  # noqa: BLE001 - visible, isolated
            self.errors.append(str(error))
            return None

    def evaluations(self):
        return tuple(self.evaluation_store.list())


__all__ = ["EvaluationSubscriber", "EvaluationStore", "InMemoryEvaluationStore"]
