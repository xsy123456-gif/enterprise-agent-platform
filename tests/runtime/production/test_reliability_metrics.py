from dataclasses import replace
from datetime import timedelta

import pytest

from app.runtime.governance.events import RuntimeEvent, RuntimeEventType
from app.runtime.governance.agent.audit import AgentGovernanceAuditSubscriber
from app.runtime.production import (
    AgentMetricsCollector,
    AgentPrincipal,
    EventDeliveryManager,
    EventDeliveryStatus,
)
from app.storage.providers.memory import InMemoryEventStore
from app.storage.providers.memory import InMemoryAuditRepository


def event(event_type="graph.started", **changes):
    base = RuntimeEvent(
        event_type=event_type,
        execution_id="execution-1", trace_id="trace-1",
        agent_id="sales_agent", agent_version="1.0",
        artifact_id="sales:1", artifact_hash="hash-1",
        backend_type="langgraph", status="started",
        deployment_version="deploy-1", runtime_policy_version="policy-1",
        quota_decision="allowed", runtime_health="healthy",
    )
    return replace(base, **changes)


class Consumer:
    def __init__(self, failures=0, consumer_id="consumer"):
        self.consumer_id = consumer_id
        self.failures = failures
        self.received = []

    def handle(self, item):
        if self.failures:
            self.failures -= 1
            raise RuntimeError("temporary")
        self.received.append(item)


def test_event_delivery_retries_consumer_failure():
    consumer = Consumer(failures=2)
    manager = EventDeliveryManager(InMemoryEventStore(), [consumer], max_attempts=3)
    record, = manager.publish(event())
    assert record.status is EventDeliveryStatus.DELIVERED
    assert record.attempts == 3
    assert len(consumer.received) == 1


def test_event_delivery_dead_letters_exhausted_consumer():
    consumer = Consumer(failures=5)
    manager = EventDeliveryManager(InMemoryEventStore(), [consumer], max_attempts=2)
    record, = manager.publish(event())
    assert record.status is EventDeliveryStatus.DEAD_LETTER
    dead_letter, = manager.list_dead_letters()
    assert dead_letter.attempts == 2
    assert dead_letter.event.event_id == record.event_id


def test_consumer_failure_is_isolated_from_other_consumers():
    broken = Consumer(failures=5, consumer_id="broken")
    healthy = Consumer(consumer_id="healthy")
    manager = EventDeliveryManager(
        InMemoryEventStore(), [broken, healthy], max_attempts=1
    )
    records = manager.publish(event())
    assert [record.status for record in records] == [
        EventDeliveryStatus.DEAD_LETTER, EventDeliveryStatus.DELIVERED,
    ]
    assert len(healthy.received) == 1


def test_event_is_persisted_once_before_retries():
    store = InMemoryEventStore()
    manager = EventDeliveryManager(store, [Consumer(failures=2)], max_attempts=3)
    item = event()
    manager.publish(item)
    assert store.query(item.execution_id) == (item,)


def test_sensitive_consumer_error_is_redacted_in_dead_letter():
    class SensitiveConsumer:
        consumer_id = "sensitive"

        def handle(self, _):
            raise RuntimeError("api_key=do-not-store")

    manager = EventDeliveryManager(
        InMemoryEventStore(), [SensitiveConsumer()], max_attempts=1
    )
    manager.publish(event())
    assert manager.list_dead_letters()[0].error == "redacted consumer failure"


def test_metrics_collect_execution_latency_and_resources():
    collector = AgentMetricsCollector()
    started = event("execution.started")
    completed = event(
        "execution.completed", timestamp=started.timestamp + timedelta(seconds=2),
        status="completed",
        payload={"token_usage": 50, "tool_calls": 2, "memory_reads": 1},
    )
    collector.handle(started)
    collector.handle(completed)
    snapshot = collector.snapshot("sales_agent")
    assert snapshot["execution_total"] == 1
    assert snapshot["success_total"] == 1
    assert snapshot["average_latency"] == 2
    assert snapshot["token_usage"] == 50
    assert snapshot["tool_calls"] == 2
    assert snapshot["memory_reads"] == 1


def test_metrics_deduplicate_graph_and_execution_completion():
    collector = AgentMetricsCollector()
    started = event("graph.started")
    collector.handle(started)
    collector.handle(event("graph.completed", status="completed"))
    collector.handle(event("execution.completed", status="completed"))
    assert collector.snapshot("sales_agent")["success_total"] == 1


@pytest.mark.parametrize(
    ("event_type", "status", "metric"),
    [
        ("execution.failed", "failed", "failure_total"),
        ("agent.authorization.denied", "denied", "authorization_denied"),
        ("approval.requested", "pending", "approval_required"),
        ("agent.context.projected", "blocked", "context_blocked"),
    ],
)
def test_metrics_project_governance_and_failure_events(event_type, status, metric):
    collector = AgentMetricsCollector()
    collector.handle(event(event_type, status=status))
    assert collector.snapshot("sales_agent")[metric] == 1


def test_runtime_event_production_evidence_round_trip():
    restored = RuntimeEvent.from_dict(event().to_dict())
    assert restored.deployment_version == "deploy-1"
    assert restored.artifact_hash == "hash-1"
    assert restored.quota_decision == "allowed"
    assert restored.runtime_health == "healthy"


@pytest.mark.parametrize(
    "event_type",
    [
        RuntimeEventType.AGENT_LIFECYCLE_CHANGED,
        RuntimeEventType.AGENT_DEPLOYMENT_STARTED,
        RuntimeEventType.AGENT_DEPLOYMENT_COMPLETED,
        RuntimeEventType.AGENT_ROLLBACK_EXECUTED,
        RuntimeEventType.AGENT_QUOTA_CHECKED,
        RuntimeEventType.AGENT_EXECUTION_REJECTED_QUOTA,
        RuntimeEventType.AGENT_HEALTH_CHANGED,
    ],
)
def test_production_audit_event_types_are_canonical(event_type):
    assert event(event_type).event_type == event_type


def test_agent_principal_is_distinct_immutable_agent_identity():
    principal = AgentPrincipal("sales_agent", "hash-1", "trusted", "registry")
    assert principal.agent_id == "sales_agent"
    assert principal.artifact_hash == "hash-1"
    with pytest.raises(Exception):
        principal.agent_id = "other"


@pytest.mark.parametrize(
    "event_type",
    [
        RuntimeEventType.AGENT_LIFECYCLE_CHANGED,
        RuntimeEventType.AGENT_DEPLOYMENT_COMPLETED,
        RuntimeEventType.AGENT_ROLLBACK_EXECUTED,
        RuntimeEventType.AGENT_QUOTA_CHECKED,
        RuntimeEventType.AGENT_HEALTH_CHANGED,
        RuntimeEventType.AGENT_EXECUTION_REJECTED_QUOTA,
    ],
)
def test_production_events_are_projected_to_existing_audit_port(event_type):
    repository = InMemoryAuditRepository()
    record = AgentGovernanceAuditSubscriber(repository).handle(event(event_type))
    assert record["event_type"] == event_type
    assert repository.query(execution_id="execution-1") == (record,)
