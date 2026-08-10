from datetime import datetime, timedelta, timezone

from app.runtime.governance.events import RuntimeEvent
from app.runtime.trace import AsyncTraceConsumer, TraceAssembler, TraceQueryService
from app.events.bus import EventBus
from app.storage.providers.memory import InMemoryTraceRepository


BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def event(event_type, offset=0, **kwargs):
    return RuntimeEvent(
        event_type=event_type, execution_id="exec-1", trace_id="trace-1",
        agent_id="sales", agent_version="1", artifact_id="artifact-a",
        artifact_hash="hash-a", backend_type="langgraph",
        status=event_type.rsplit(".", 1)[-1],
        timestamp=BASE + timedelta(milliseconds=offset), **kwargs,
    )


def test_assembles_execution_graph_node_and_loop_spans():
    repository = InMemoryTraceRepository()
    assembler = TraceAssembler(repository)
    assembler.consume(event("execution.started"))
    assembler.consume(event("graph.started", 1, operation_id="graph-1"))
    assembler.consume(event("node.started", 2, node_id="reasoning", operation_id="node-1"))
    assembler.consume(event("node.completed", 4, node_id="reasoning", operation_id="node-1"))
    assembler.consume(event("node.started", 5, node_id="reasoning", operation_id="node-2"))
    assembler.consume(event("node.completed", 8, node_id="reasoning", operation_id="node-2"))
    assembler.consume(event("graph.completed", 9, operation_id="graph-1"))
    assembler.consume(event("execution.completed", 10))
    trace = repository.get("trace-1")
    reasoning = [span for span in repository.list_spans("trace-1") if getattr(span, "name", None) == "reasoning"]
    assert trace.status == "OK"
    assert trace.artifact_hash == "hash-a"
    assert len(reasoning) == 2
    assert all(span.status == "OK" and span.duration_ms >= 0 for span in reasoning)


def test_tool_parent_status_and_sensitive_payload_filtering():
    repository = InMemoryTraceRepository()
    assembler = TraceAssembler(repository)
    assembler.consume(event("node.started", node_id="tool", operation_id="node-tool"))
    assembler.consume(event(
        "tool.called", 1, operation_id="call-1",
        payload={"tool": "crm_query", "request_id": "call-1",
                 "api_key": "forbidden", "raw_customer_records": [1, 2]},
    ))
    assembler.consume(event(
        "tool.denied", 2, operation_id="call-1",
        payload={"tool": "crm_query", "request_id": "call-1"},
    ))
    spans = repository.list_spans("trace-1")
    node = next(span for span in spans if getattr(span, "operation_id", None) == "node-tool")
    tool = next(span for span in spans if getattr(span, "operation_id", None) == "call-1")
    assert tool.parent_span_id == node.span_id
    assert tool.status == "DENIED"
    timeline = TraceQueryService(repository).timeline("trace-1")
    assert timeline[1]["attributes"] == {"tool": "crm_query", "request_id": "call-1"}


def test_memory_event_can_arrive_after_execution_completed():
    repository = InMemoryTraceRepository()
    assembler = TraceAssembler(repository)
    assembler.consume(event("execution.completed"))
    assembler.consume(event("memory.write.requested", 1))
    assembler.consume(event("memory.write.completed", 2, payload={"result_count": 2}))
    trace = repository.get("trace-1")
    memory = [span for span in repository.list_spans("trace-1") if getattr(span, "span_type", None) == "MEMORY"]
    assert trace.status == "OK"
    assert len(memory) == 1 and memory[0].status == "OK"


def test_trace_failure_is_isolated_and_does_not_block_independent_audit():
    class FailingAssembler:
        def consume(self, runtime_event):
            raise RuntimeError("trace unavailable")

    class Audit:
        def __init__(self):
            self.events = []

        def handle(self, runtime_event):
            self.events.append(runtime_event.event_type)

    bus, audit = EventBus(), Audit()
    trace = AsyncTraceConsumer(FailingAssembler())
    bus.subscribe(trace)
    bus.subscribe(audit)
    bus.publish(event("execution.started"))
    trace.drain(1)
    assert trace.errors == ["trace unavailable"]
    assert audit.events == ["execution.started"]
    trace.close()
