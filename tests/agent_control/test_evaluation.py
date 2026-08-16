"""Phase 13.7 Evaluation Platform tests."""

from app.platform.agent_control.evaluation import (
    AgentEvaluation,
    AgentEvaluationStore,
)


def test_evaluation_summary():
    store = AgentEvaluationStore()
    store.record(AgentEvaluation(
        evaluation_id="e1", agent_id="commerce_agent", agent_version="1.0",
        task_success=True, tool_calls=2, latency_ms=100, token_cost=0.01,
        feedback=4.0))
    store.record(AgentEvaluation(
        evaluation_id="e2", agent_id="commerce_agent", agent_version="1.0",
        task_success=False, tool_calls=4, latency_ms=200, token_cost=0.03,
        feedback=2.0))
    summary = store.summary("commerce_agent")
    assert summary.total_executions == 2
    assert summary.success_rate == 0.5
    assert summary.avg_tool_calls == 3.0
    assert summary.avg_latency_ms == 150.0
    assert summary.total_token_cost == 0.04
    assert summary.avg_feedback == 3.0


def test_evaluation_empty_summary():
    store = AgentEvaluationStore()
    summary = store.summary("sales_agent")
    assert summary.total_executions == 0
    assert summary.avg_feedback is None


def test_evaluation_validation():
    import pytest
    with pytest.raises(ValueError):
        AgentEvaluation(evaluation_id="e", agent_id="a", agent_version="1.0",
                        tool_calls=-1)
