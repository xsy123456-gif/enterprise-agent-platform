import pytest

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.governance.adapters import (
    ApprovalAdapter,
    ExecutionCheckpoint,
    InMemoryExecutionCheckpointStore,
)
from app.governance.adapters.runtime_events import RuntimeGovernanceEmitter
from app.runtime.governance.adapters.runtime_event_mapper import RuntimeEventContext
from app.events.bus import EventBus
from app.storage.providers.memory.event import InMemoryEventStore
from app.runtime.backends.langgraph import build_graph
from app.runtime.backends.langgraph.nodes import GuardNode, GovernanceGate


class ToolIntent:
    def __call__(self, state):
        if (state.get("observation") or
                (state.get("intermediate_results") or {}).get("observations")):
            return {"reasoning_output": {"action": "finish", "output": "tool ran"}}
        return {
            "reasoning_output": {
                "action": "tool_call",
                "tool": "crm_query",
                "arguments": {"customer": "A"},
            }
        }


class FakeTool:
    def __call__(self, state):
        return {"response": "tool ran", "observation": "tool ran", "status": "completed"}


def initial_state(text="准备客户资料"):
    return {
        "trace_id": "trace-1", "execution_id": "exec-1", "agent_id": "sales",
        "agent_version": "1", "input": text, "messages": [], "metadata": {},
    }


def test_guard_allows_normal_request():
    result = GuardNode()(initial_state())
    assert result["guard_result"]["action"] == "allow"


def test_high_risk_request_requires_approval():
    state = initial_state("导出全部财务数据")
    guarded = GuardNode()(state)
    decision = GovernanceGate()(dict(state, **guarded, pending_tool_call={"tool": "crm_query"}))
    assert decision["governance_decision"]["status"] == "require_approval"


def test_interrupt_approval_resume_and_reject():
    saver = MemorySaver()
    checkpoints = InMemoryExecutionCheckpointStore()
    from app.runtime.backends.langgraph.nodes import ApprovalInterruptNode
    graph = build_graph(reasoning_node=ToolIntent(), tool_node=FakeTool(),
                        approval_node=ApprovalInterruptNode(checkpoint_store=checkpoints),
                        checkpointer=saver)
    config = {"configurable": {"thread_id": "exec-1"}}
    first = graph.invoke(initial_state("导出全部财务数据"), config)
    assert first.get("__interrupt__")
    assert checkpoints.load("exec-1").current_node == "approval"
    resumed = graph.invoke(Command(resume={"approved": False}), config)
    assert resumed["status"] == "failed"
    assert "denied" in resumed["response"]


def test_interrupt_approval_resume_and_approve_runs_tool():
    saver = MemorySaver()
    graph = build_graph(reasoning_node=ToolIntent(), tool_node=FakeTool(), checkpointer=saver)
    config = {"configurable": {"thread_id": "exec-2"}}
    first = graph.invoke(initial_state("导出全部财务数据"), config)
    assert first.get("__interrupt__")
    resumed = graph.invoke(Command(resume={"approved": True}), config)
    assert resumed["status"] == "completed"
    assert resumed["response"] == "tool ran"


def test_execution_checkpoint_contract_round_trip():
    store = InMemoryExecutionCheckpointStore()
    checkpoint = ExecutionCheckpoint(
        execution_id="exec-1", graph_state={"status": "waiting"},
        current_node="approval", pending_action={"tool": "crm_query"}, approval_id="a-1",
    )
    store.save(checkpoint)
    assert store.load("exec-1") == checkpoint
    store.delete("exec-1")
    assert store.load("exec-1") is None


def test_governance_events_use_canonical_bus_and_store():
    bus, store = EventBus(), InMemoryEventStore()
    context = RuntimeEventContext(
        execution_id="exec-1", trace_id="trace-1", agent_id="sales",
        agent_version="1", artifact_id="artifact-1", artifact_hash="hash-1",
        backend_type="langgraph",
    )
    emitter = RuntimeGovernanceEmitter(context, bus, store)
    emitter.emit("guard.checked", "completed", {"risk": "low"})
    emitter.emit("governance.checked", "completed", {"status": "allow"})
    assert [e.event_type for e in store.query("exec-1")] == [
        "guard.checked", "governance.checked"
    ]
    assert [e["event_type"] for e in bus.get_events()] == [
        "guard.checked", "governance.checked"
    ]
