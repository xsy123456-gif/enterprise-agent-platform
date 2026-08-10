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
    )

    trace = assembler.consume(RuntimeEvent.from_dict(event.to_dict()))
    spans = repository.list_spans("trace-1")

    assert trace.parent_agent_id == "supervisor"
    assert trace.agent_execution_id == "agent-execution-1"
    assert all(span.parent_agent_id == "supervisor" for span in spans)
    assert all(span.agent_execution_id == "agent-execution-1" for span in spans)
