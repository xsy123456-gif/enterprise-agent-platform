from app.runtime.governance.events import RuntimeEvent
from app.runtime.trace import TraceAssembler
from app.storage.providers.memory import InMemoryTraceRepository


def test_agent_trace_identity_is_preserved_without_backend_coupling():
    repository = InMemoryTraceRepository()
    assembler = TraceAssembler(repository)
    event = RuntimeEvent(
        event_type="graph.started",
        execution_id="execution-1",
        trace_id="trace-1",
        agent_id="finance_agent",
        agent_version="1.0",
        artifact_id="finance:1.0:langgraph:abc",
        artifact_hash="a" * 64,
        backend_type="langgraph",
        status="started",
        parent_agent_id="supervisor",
        agent_execution_id="agent-execution-1",
        invocation_id="invocation-1",
        message_id="message-1",
        payload={
            "sender_agent_id": "sales_agent",
            "receiver_agent_id": "finance_agent",
            "message_type": "RESULT",
            "payload_size": 42,
        },
    )

    trace = assembler.consume(RuntimeEvent.from_dict(event.to_dict()))
    spans = repository.list_spans("trace-1")

    assert trace.parent_agent_id == "supervisor"
    assert trace.agent_execution_id == "agent-execution-1"
    assert trace.invocation_id == "invocation-1"
    assert trace.message_id == "message-1"
    assert all(span.parent_agent_id == "supervisor" for span in spans)
    assert all(span.agent_execution_id == "agent-execution-1" for span in spans)


def test_message_event_is_traceable_without_persisting_full_payload():
    repository = InMemoryTraceRepository()
    assembler = TraceAssembler(repository)
    event = RuntimeEvent(
        event_type="agent.message.created",
        execution_id="execution-1", trace_id="trace-message",
        agent_id="finance_agent", agent_version="1.0",
        artifact_id="finance:1.0:langgraph:abc", artifact_hash="a" * 64,
        backend_type="langgraph", status="created",
        invocation_id="invocation-1", message_id="message-1",
        payload={"sender_agent_id": "sales_agent", "payload_size": 10,
                 "raw_payload": "must not be stored"},
    )

    assembler.consume(event)
    spans = repository.list_spans("trace-message")
    message_span = next(span for span in spans if span.span_type == "MESSAGE")

    assert message_span.message_id == "message-1"
    assert "raw_payload" not in message_span.attributes
