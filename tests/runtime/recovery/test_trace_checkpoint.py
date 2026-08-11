from app.governance.adapters.checkpoint import PersistentCheckpointStore
from app.runtime.governance.events import RuntimeEvent
from app.runtime.trace import TraceAssembler
from app.storage.providers.memory import InMemoryTraceRepository


def test_recovery_trace_correlation_is_preserved_without_error_payload():
    repository = InMemoryTraceRepository()
    event = RuntimeEvent(
        event_type="agent.retry.requested",
        execution_id="execution-1", trace_id="trace-recovery",
        agent_id="finance", agent_version="1.0",
        artifact_id="finance:1.0:langgraph:a", artifact_hash="a" * 64,
        backend_type="multi_agent", status="requested",
        agent_execution_id="agent-execution-1", invocation_id="invocation-1",
        attempt_id="attempt-1", failure_id="failure-1", retry_number=1,
        recovery_action="RETRY",
    )
    trace = TraceAssembler(repository).consume(event)
    recovery_span = next(
        span for span in repository.list_spans(trace.trace_id)
        if span.span_type == "RECOVERY"
    )
    assert recovery_span.attempt_id == "attempt-1"
    assert recovery_span.failure_id == "failure-1"
    assert recovery_span.retry_number == 1
    assert recovery_span.recovery_action == "RETRY"
    assert recovery_span.attributes == {}


def test_failure_trace_span_is_marked_error():
    repository = InMemoryTraceRepository()
    event = RuntimeEvent(
        event_type="agent.failure.detected",
        execution_id="execution-1", trace_id="trace-failure",
        agent_id="finance", agent_version="1.0",
        artifact_id="finance:1.0:langgraph:a", artifact_hash="a" * 64,
        backend_type="multi_agent", status="failed",
        attempt_id="attempt-1", failure_id="failure-1",
    )
    TraceAssembler(repository).consume(event)
    span = next(
        item for item in repository.list_spans("trace-failure")
        if item.span_type == "RECOVERY"
    )
    assert span.status == "ERROR"


def test_existing_postgres_checkpoint_schema_is_extended_not_replaced():
    schema = PersistentCheckpointStore.SCHEMA
    assert "execution_checkpoints" in schema
    assert "failed_agent_execution_id" in schema
    assert "failed_node" in schema
    assert "retry_attempt" in schema
