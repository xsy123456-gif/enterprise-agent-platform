"""Phase 17.1 Evaluation Intelligence tests."""

import pytest

from app.platform.intelligence.evaluation import (
    EvaluationEngine,
    EvaluationMetric,
    EvaluationMetricRegistry,
    ExecutionSample,
)


def test_execution_quality_evaluation():
    engine = EvaluationEngine()
    samples = [
        ExecutionSample(success=True, latency_ms=100.0, cost=0.5),
        ExecutionSample(success=False, latency_ms=200.0, cost=0.5),
        ExecutionSample(success=True, latency_ms=150.0, cost=0.5),
    ]
    evaluation = engine.evaluate_execution_quality(
        "e1", "commerce_agent", "1.0", samples)
    assert evaluation.evaluation_type == "execution_quality"
    assert evaluation.score == pytest.approx(2 / 3)
    assert evaluation.metrics["success_rate"] == pytest.approx(2 / 3)
    assert evaluation.metrics["failure_rate"] == pytest.approx(1 / 3)
    assert evaluation.metrics["avg_latency_ms"] == pytest.approx(150.0)


def test_empty_samples_score_zero():
    engine = EvaluationEngine()
    evaluation = engine.evaluate_execution_quality("e1", "a", "1.0", [])
    assert evaluation.score == 0.0


def test_metric_registry_versioned():
    registry = EvaluationMetricRegistry()
    registry.register(EvaluationMetric(
        metric_id="success_rate", name="Success Rate", category="reliability",
        formula="success/total", version="1.0", threshold=0.9))
    metric = registry.get("success_rate")
    assert metric.name == "Success Rate"
    assert metric.threshold == 0.9


def test_evaluation_score_range():
    from app.platform.intelligence.evaluation import AgentEvaluation
    with pytest.raises(ValueError):
        AgentEvaluation(evaluation_id="e", agent_id="a", agent_version="1.0",
                        evaluation_type="execution_quality", score=1.5)
