"""Phase 18.8 Runtime -> Production Observability bridge tests.

Verify that a real Commerce Agent execution automatically produces a Trace and
Metrics with the same execution_id as the ExecutionRecord — without the test
calling any collector manually.
"""

import uuid

import pytest

from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics.plans import FakeFactQueryExecutor
from app.commerce.skills import (
    DiagnosticSkillExecutionAdapter,
    SkillExecutionContext,
    build_skill_system,
)
from app.events.bus import EventBus
from app.platform.production.observability import (
    AgentMetricsCollector,
    ExecutionSpan,
    ProductionObservabilitySubscriber,
    TraceCollector,
)
from app.runtime.execution import ExecutionManager, ExecutionStatus, InMemoryExecutionStore

SUBJECT = SubjectRef("STORE", "JP01")


def _facts():
    return {
        ("commerce.metrics.read", "GMV", "JP01"): {"records": [{"value": 1000.0}]},
        ("commerce.metrics.read", "GMV_B", "JP01"): {"records": [{"value": 2000.0}]},
        ("commerce.metrics.read", "ORDERS", "JP01"): {"records": [{"value": 20.0}]},
        ("commerce.metrics.read", "ORDERS_B", "JP01"): {"records": [{"value": 40.0}]},
        ("commerce.metrics.read", "SESSIONS", "JP01"): {"records": [{"value": 1000.0}]},
        ("commerce.metrics.read", "SESSIONS_B", "JP01"): {"records": [{"value": 1000.0}]},
    }


@pytest.fixture(scope="module")
def skill_system():
    return build_skill_system()


def _wired(skill_system):
    event_bus = EventBus()
    trace = TraceCollector()
    metrics = AgentMetricsCollector()
    subscriber = ProductionObservabilitySubscriber(trace, metrics)
    event_bus.subscribe(subscriber)
    manager = ExecutionManager(InMemoryExecutionStore(), event_bus=event_bus)
    adapter = DiagnosticSkillExecutionAdapter(skill_system, execution_manager=manager)
    return adapter, manager, trace, metrics


def test_real_agent_execution_automatically_produces_trace_and_metrics(skill_system):
    adapter, manager, trace, metrics = _wired(skill_system)
    execution_id = uuid.uuid4().hex
    context = SkillExecutionContext(
        execution_id=execution_id, trace_id="trace-1", tenant_id="company_A",
        agent_id="commerce_operations_agent", agent_version="1.0",
        principal_id="U001",
    )
    adapter.execute(context, "store_performance_diagnosis", SUBJECT,
                    fact_executor=FakeFactQueryExecutor(_facts()))

    # automatic: no manual trace/metric recording anywhere
    record = manager.store.get(execution_id)
    assert record is not None
    assert record.status == ExecutionStatus.COMPLETED

    trace_record = trace.trace("trace-1")
    assert trace_record is not None
    assert trace_record.execution_id == execution_id
    assert trace_record.agent_id == "commerce_operations_agent"

    samples = metrics.samples("commerce_operations_agent")
    assert samples
    assert samples[0].execution_id == execution_id
    assert samples[0].success is True


def test_failure_execution_produces_failure_observation(skill_system):
    adapter, manager, trace, metrics = _wired(skill_system)
    execution_id = uuid.uuid4().hex
    context = SkillExecutionContext(
        execution_id=execution_id, trace_id="trace-2", tenant_id="company_A",
        agent_id="commerce_operations_agent", agent_version="1.0",
    )
    with pytest.raises(Exception):
        adapter.execute(context, "store_performance_diagnosis", SUBJECT,
                        fact_executor=None)

    record = manager.store.get(execution_id)
    assert record.status == ExecutionStatus.FAILED
    assert trace.trace("trace-2").status == "FAILED"
    samples = metrics.samples("commerce_operations_agent")
    assert samples and samples[-1].success is False


def test_observability_does_not_reexecute_business_logic(skill_system):
    # The subscriber only maps events; it has no runner/agent reference and never
    # invokes a skill.  Re-publishing an event must not re-run anything.
    trace = TraceCollector()
    metrics = AgentMetricsCollector()
    from app.runtime.governance.events import RuntimeEvent
    event = RuntimeEvent(
        event_type="execution.created", execution_id="e1", trace_id="t1",
        agent_id="a", agent_version="1.0", artifact_id="art", artifact_hash="h",
        backend_type="skill", status="created", tenant_id="company_A",
    )
    subscriber = ProductionObservabilitySubscriber(trace, metrics)
    subscriber.handle(event)
    subscriber.handle(event)  # idempotent observation, no side effect
    assert trace.trace("t1") is not None


def test_trace_does_not_contain_secret():
    # A span with secret metadata is rejected at construction.
    with pytest.raises(ValueError):
        ExecutionSpan(span_id="s1", trace_id="t1", component="agent",
                      metadata={"authorization": "Bearer abc"})
