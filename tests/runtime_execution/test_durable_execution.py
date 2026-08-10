from types import SimpleNamespace

import pytest

from app.governance.adapters import InMemoryExecutionCheckpointStore
from app.runtime.execution import (
    ExecutionManager, ExecutionStatus, InMemoryExecutionStore,
)
from app.runtime.dispatcher import (
    AgentRuntimeStateFactory, BackendArtifactResolver, RuntimeDispatcher,
)
from app.runtime.ports import GraphRuntime
from app.runtime.contracts import ExecutionResult
from app.runtime.selector import RuntimeSelector
from app.runtime.governance.events import RuntimeEventType
from app.storage.providers.memory import InMemoryEventStore


def state():
    return SimpleNamespace(
        task_id="exec-1", execution_id="exec-1", trace_id="trace-1",
        agent_id="sales_agent", agent_version="1", tenant_id="tenant-1",
        user_id="user-1", current_node="context",
    )


def artifact():
    return SimpleNamespace(artifact_id="sales:1:langgraph")


def test_execution_lifecycle_and_history():
    store = InMemoryExecutionStore()
    events = InMemoryEventStore()
    manager = ExecutionManager(store, event_store=events)
    record = manager.create(state(), artifact())
    assert record.status is ExecutionStatus.CREATED
    manager.transition("exec-1", "running", "context")
    manager.transition("exec-1", "completed", "end")
    assert store.get("exec-1").status is ExecutionStatus.COMPLETED
    assert [item.status for item in store.list_history("exec-1")] == [
        ExecutionStatus.CREATED, ExecutionStatus.RUNNING, ExecutionStatus.COMPLETED,
    ]
    assert [event.event_type for event in events.query("exec-1")] == [
        RuntimeEventType.EXECUTION_CREATED,
        RuntimeEventType.EXECUTION_STARTED,
        RuntimeEventType.EXECUTION_COMPLETED,
    ]


def test_checkpoint_save_and_resume_contract():
    store = InMemoryExecutionStore()
    checkpoints = InMemoryExecutionCheckpointStore()
    manager = ExecutionManager(store, checkpoint_store=checkpoints)
    manager.create(state(), artifact())
    manager.transition("exec-1", "running", "tool")
    manager.transition("exec-1", "waiting_approval", "approval")
    manager.save_checkpoint(
        "exec-1", {"execution_id": "exec-1", "status": "waiting"},
        current_node="approval", pending_action={"tool": "crm_query"},
    )
    seen = {}
    result = manager.resume(
        "exec-1", {"approved": True},
        lambda checkpoint, approval: seen.update(
            checkpoint=checkpoint, approval=approval
        ) or "continued",
    )
    assert result == "continued"
    assert seen["checkpoint"].current_node == "approval"
    assert seen["approval"] == {"approved": True}


def test_invalid_transition_is_rejected():
    manager = ExecutionManager(InMemoryExecutionStore())
    manager.create(state(), artifact())
    with pytest.raises(ValueError, match="Invalid execution transition"):
        manager.transition("exec-1", "completed")


def test_dispatcher_records_execution_when_manager_is_injected():
    class Backend(GraphRuntime):
        def execute(self, artifact, runtime_state):
            return ExecutionResult(
                runtime_state.task_id, "completed", "ok", runtime_state
            )

    backend = Backend()
    artifact_record = SimpleNamespace(
        artifact_id="sales:1:current", agent_id="sales_agent", agent_version="1",
        backend_type="current", artifact_hash="hash",
    )
    manager = ExecutionManager(InMemoryExecutionStore())
    dispatcher = RuntimeDispatcher(
        RuntimeSelector({"current": backend}, default_backend="current"),
        BackendArtifactResolver({("sales_agent", "1", "current"): artifact_record}),
        AgentRuntimeStateFactory(), execution_manager=manager,
    )
    context = SimpleNamespace(
        task_id="exec-1", trace_id="trace-1", tenant_id="tenant-1",
        task="task", user_id="user-1", role="sales", step_id="1",
        capability="customer_analysis", goal="task", memory_context=[],
        messages=[], tool_results=[], department_id=None,
        agent_definition=SimpleNamespace(allowed_tools=[]),
    )
    result = dispatcher.execute_step(context, "sales_agent", "1")
    assert result.response == "ok"
    assert manager.store.get("exec-1").status is ExecutionStatus.COMPLETED
