from dataclasses import dataclass
from threading import Event
from types import SimpleNamespace

from app.compiler.backend.models import BackendArtifact
from app.events.bus import EventBus
from app.runtime.backends.langgraph import LangGraphResponseEventHook, LangGraphRuntimeAdapter
from app.runtime.backends.langgraph.state import GraphState
from app.runtime.contracts import AgentRuntimeState
from app.runtime.memory import AsyncMemoryEventConsumer, MemoryEventAdapter
from app.storage.providers.memory import InMemoryEventStore


@dataclass
class Receipt:
    event_id: str = "memory-1"
    accepted: bool = True


class BlockingMemory:
    def __init__(self, fail=False):
        self.fail = fail
        self.started = Event()
        self.release = Event()
        self.requests = []

    def write(self, request):
        self.started.set()
        self.release.wait(2)
        if self.fail:
            raise RuntimeError("memory unavailable")
        self.requests.append(request)
        return Receipt()


class FinishGraph:
    def invoke(self, graph_state, config=None):
        return {**graph_state, "response": "客户A风险较低", "status": "completed"}


def artifact():
    return BackendArtifact.create(
        agent_id="sales_agent", agent_version="1", backend_type="langgraph",
        backend_version="1", compiler_version="1", graph_ir_hash="ir",
        runtime_definition={"schema_version": "langgraph.backend/v1"},
    )


def state():
    return AgentRuntimeState(
        task_id="task-1", trace_id="trace-1", tenant_id="tenant-1",
        agent_id="sales_agent", agent_version="1", execution_id="exec-1",
        user_id="user-1", department_id="sales",
        request_context={"input": "分析客户A", "subject_id": "user-1"},
        permission_context={"permissions": ["crm.customer.read"]},
        policy_context={"memory_write": True},
    )


def result(runtime_state):
    completed = runtime_state.patched({
        "response": "客户A风险较低", "tool_results": [{"customer": "A"}],
    })
    return SimpleNamespace(response=completed.response, state=completed)


def wire(memory):
    bus, store = EventBus(), InMemoryEventStore()
    consumer = AsyncMemoryEventConsumer(memory, event_bus=bus, event_store=store)
    bus.subscribe(consumer)
    return LangGraphResponseEventHook(bus, store), consumer, store


def test_response_event_is_adapted_to_governed_memory_write():
    memory = BlockingMemory()
    hook, consumer, store = wire(memory)
    runtime_state = state()
    hook.emit(artifact(), runtime_state, result(runtime_state))
    assert memory.started.wait(1)
    memory.release.set()
    consumer.drain(1)
    request = memory.requests[0]
    assert request.scope.tenant_id == "tenant-1"
    assert request.principal.user_id == "user-1"
    assert request.metadata["execution_id"] == "exec-1"
    assert request.metadata["permission_context"] == {
        "permissions": ["crm.customer.read"]
    }
    assert [event.event_type for event in store.query("exec-1")] == [
        "response.completed", "memory.write.requested", "memory.write.completed"
    ]
    consumer.close()


def test_langgraph_adapter_emits_response_completed_hook():
    memory = BlockingMemory()
    hook, consumer, store = wire(memory)
    runtime = LangGraphRuntimeAdapter(graph=FinishGraph(), response_event_hook=hook)
    execution = runtime.execute(artifact(), state())
    assert execution.status == "completed"
    assert memory.started.wait(1)
    memory.release.set()
    consumer.drain(1)
    assert store.query("exec-1", "response.completed")
    assert store.query("exec-1", "memory.write.completed")
    consumer.close()


def test_memory_write_is_async_and_failure_does_not_change_response():
    memory = BlockingMemory(fail=True)
    hook, consumer, store = wire(memory)
    runtime_state = state()
    execution_result = result(runtime_state)
    event = hook.emit(artifact(), runtime_state, execution_result)
    assert event.payload["output"] == "客户A风险较低"
    assert memory.started.wait(1)
    assert "memory.write.failed" not in [e.event_type for e in store.query("exec-1")]
    memory.release.set()
    consumer.drain(1)
    assert execution_result.response == "客户A风险较低"
    assert [e.event_type for e in store.query("exec-1")][-1] == "memory.write.failed"
    consumer.close()


def test_graph_state_does_not_own_memory_data_or_policy():
    forbidden = {"memory_context", "memory_items", "memory_policy"}
    assert forbidden.isdisjoint(GraphState.__annotations__)


def test_adapter_rejects_anonymous_memory_write():
    runtime_state = state()
    event = LangGraphResponseEventHook().emit(
        artifact(), runtime_state.patched({"user_id": None}), result(runtime_state)
    )
    try:
        MemoryEventAdapter().adapt(event)
    except ValueError as error:
        assert "user_id" in str(error)
    else:
        raise AssertionError("anonymous Memory write must be rejected")
