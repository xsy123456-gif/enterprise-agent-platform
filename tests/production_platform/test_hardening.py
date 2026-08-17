"""Phase 15.7 Production Hardening + E2E."""

import pytest

from app.platform.production.audit import ProductionAuditLogger
from app.platform.production.errors import (
    BudgetExceededError,
    QuotaExceededError,
    TenantIsolationViolationError,
)
from app.platform.production.governance import AgentBudgetPolicy, BudgetManager
from app.platform.production.observability import (
    AgentCostRecord,
    AgentMetricSample,
    AgentMetricsCollector,
    ExecutionSpan,
    TraceCollector,
)
from app.platform.production.reliability import (
    CircuitBreaker,
    RecoveryManager,
    RetryPolicy,
    retry_call,
)
from app.platform.production.tenant import (
    QuotaManager,
    TenantIsolation,
    TenantQuota,
)


# ── Production E2E ──────────────────────────────────────────

def test_production_e2e_flow():
    trace = TraceCollector()
    metrics = AgentMetricsCollector()
    audit = ProductionAuditLogger()
    isolation = TenantIsolation()
    quota = QuotaManager([TenantQuota(tenant_id="company_A", max_execution=100)])
    budget = BudgetManager([AgentBudgetPolicy(
        agent_id="commerce_agent", daily_limit=10.0, hard_stop=True)])

    # 1. trace a full agent execution
    trace.start_trace(trace_id="t1", tenant_id="company_A",
                      agent_id="commerce_agent", agent_version="1.0",
                      task_id="task1")
    trace.add_span(ExecutionSpan(span_id="s1", trace_id="t1", component="skill",
                                 operation="store_diagnosis", duration=40.0))
    trace.add_span(ExecutionSpan(span_id="s2", trace_id="t1", component="tool",
                                 operation="metric.query", duration=5.0))
    trace.finish_trace("t1", status="SUCCESS")

    # 2. tenant isolation + quota
    isolation.ensure_owner("company_A", "company_A")
    quota.consume("company_A", "execution", 1)

    # 3. cost + budget
    budget.record(AgentCostRecord(
        execution_id="e1", tenant_id="company_A", agent_id="commerce_agent",
        llm_cost=1.0, total_cost=1.0))

    # 4. metrics + audit
    metrics.record(AgentMetricSample(
        tenant_id="company_A", agent_id="commerce_agent", success=True,
        latency_ms=45.0, token_usage=100, tool_cost=0.5, feedback=5.0))
    audit.record("company_A", "commerce_agent", "AgentExecuted", trace_id="t1")

    assert trace.trace("t1").status == "SUCCESS"
    assert len(trace.spans_for("t1")) == 2
    assert metrics.summary("commerce_agent").success_rate == 1.0
    assert len(audit.list()) == 1


# ── Security hardening ──────────────────────────────────────

def test_cross_tenant_isolation_rejected():
    isolation = TenantIsolation()
    with pytest.raises(TenantIsolationViolationError):
        isolation.ensure_owner("company_A", "company_B")


def test_trace_never_leaks_secret():
    trace = TraceCollector()
    trace.start_trace("t1", tenant_id="company_A", agent_id="a")
    with pytest.raises(ValueError):
        trace.add_span(ExecutionSpan(span_id="s1", trace_id="t1",
                                     component="llm", metadata={"secret": "x"}))


def test_audit_never_contains_secret():
    audit = ProductionAuditLogger()
    record = audit.record("company_A", "commerce_agent", "AgentExecuted")
    for forbidden in ("secret", "credential", "token", "private", "password"):
        assert forbidden not in record.to_dict()
        assert not hasattr(record, forbidden)


# ── Replay ──────────────────────────────────────────────────

def test_replay_captures_versions_and_trace():
    trace = TraceCollector()
    trace.start_trace(trace_id="t1", tenant_id="company_A",
                      agent_id="commerce_agent", agent_version="1.0",
                      task_id="task1")
    finished = trace.finish_trace("t1", status="SUCCESS")
    # replay requires agent_version + trace_id to be recorded
    assert finished.agent_version == "1.0"
    assert finished.trace_id == "t1"
    assert finished.end_time


# ── Reliability hardening (failure visible) ─────────────────

def test_failure_is_visible_not_swallowed():
    class _TransientError(Exception):
        pass

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        raise _TransientError("down")

    with pytest.raises(_TransientError):
        retry_call(flaky, RetryPolicy(max_retry=2,
                                      retryable_errors=(_TransientError,)),
                   sleep=lambda s: None)
    assert calls["n"] == 3  # exhausted, raised — never swallowed


def test_recovery_manager_escalation_visible():
    manager = RecoveryManager()

    def fail():
        raise RuntimeError("boom")

    manager.run("task1", fail, fallback=lambda: 1 / 0,
                escalate=lambda: "human")
    assert manager.escalations == ["task1"]


# ── SLA ─────────────────────────────────────────────────────

def test_sla_from_metrics():
    collector = AgentMetricsCollector()
    for i in range(10):
        collector.record(AgentMetricSample(
            tenant_id="company_A", agent_id="commerce_agent",
            success=(i < 9), latency_ms=float(i)))
    sla = collector.sla("commerce_agent")
    assert sla.success_rate == 0.9
    assert sla.availability == pytest.approx(0.9)
    assert sla.latency_p95 >= 0.0
