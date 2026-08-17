"""Phase 15.1 Observability Foundation tests."""

import pytest

from app.platform.production.observability import (
    AgentMetricSample,
    AgentMetricsCollector,
    AgentTrace,
    CostCollector,
    ExecutionSpan,
    TraceCollector,
)


def test_trace_span_lifecycle():
    collector = TraceCollector()
    trace = collector.start_trace(
        trace_id="t1", tenant_id="company_A", agent_id="commerce_agent",
        agent_version="1.0", task_id="task1")
    assert trace.status == "RUNNING"
    span = collector.add_span(ExecutionSpan(
        span_id="s1", trace_id="t1", component="tool", operation="metric.query",
        duration=12.5))
    assert collector.spans_for("t1") == (span,)
    finished = collector.finish_trace("t1", status="SUCCESS")
    assert finished.status == "SUCCESS"
    assert finished.end_time


def test_span_rejects_sensitive_metadata():
    with pytest.raises(ValueError):
        ExecutionSpan(span_id="s1", trace_id="t1", component="llm",
                      metadata={"token": "x"})
    with pytest.raises(ValueError):
        ExecutionSpan(span_id="s1", trace_id="t1", component="llm",
                      metadata={"credential": "y"})


def test_span_requires_known_trace():
    collector = TraceCollector()
    with pytest.raises(ValueError):
        collector.add_span(ExecutionSpan(
            span_id="s1", trace_id="nope", component="agent"))


def test_metrics_collector_summary_and_sla():
    collector = AgentMetricsCollector()
    collector.record(AgentMetricSample(
        tenant_id="company_A", agent_id="commerce_agent", success=True,
        latency_ms=100.0, retry_count=0, token_usage=100, tool_cost=0.5,
        feedback=4.0))
    collector.record(AgentMetricSample(
        tenant_id="company_A", agent_id="commerce_agent", success=False,
        latency_ms=200.0, retry_count=2, token_usage=200, tool_cost=0.5))
    summary = collector.summary("commerce_agent")
    assert summary.total == 2
    assert summary.success_rate == 0.5
    assert summary.failure_rate == 0.5
    assert summary.total_retry_count == 2
    assert summary.total_token_usage == 300
    assert summary.avg_feedback == 4.0
    sla = collector.sla("commerce_agent")
    assert sla.success_rate == 0.5


def test_cost_collector_aggregates_per_tenant():
    from app.platform.production.observability import AgentCostRecord
    collector = CostCollector()
    collector.record(AgentCostRecord(
        execution_id="e1", tenant_id="company_A", agent_id="finance_agent",
        llm_cost=0.1, tool_cost=0.05, total_cost=0.15))
    collector.record(AgentCostRecord(
        execution_id="e2", tenant_id="company_B", agent_id="finance_agent",
        llm_cost=0.2, tool_cost=0.1, total_cost=0.3))
    assert collector.total_for("finance_agent", tenant_id="company_A") == pytest.approx(0.15)
    assert collector.total_for("finance_agent") == pytest.approx(0.45)
