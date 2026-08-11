from app.governance.adapters import ApprovalAdapter
from app.runtime.execution import ExecutionManager, InMemoryExecutionStore
from app.runtime.execution.models import ExecutionRecord, ExecutionStatus
from app.runtime.governance.agent import (
    AgentAuthorizationEngine,
    AgentGovernanceAuditor,
    AgentGovernanceGate,
    GovernedAgentRuntimeInvoker,
    TrustLevel,
    AgentGovernanceAuditSubscriber,
)
from app.runtime.multi_agent import AgentRuntimeInvoker
from app.runtime.trace import TraceAssembler
from app.storage.providers.memory import (
    InMemoryAuditRepository, InMemoryEventStore, InMemoryTraceRepository,
)
from tests.runtime.governance.agent.helpers import (
    envelope, node, policy_store, principal, request, result,
)


class RecordingInvoker(AgentRuntimeInvoker):
    def __init__(self):
        self.calls = []

    def invoke(self, agent_node, invocation):
        self.calls.append(invocation)
        return result(agent_node, invocation)


def governed(policy_overrides=None, execution_manager=None):
    events = InMemoryEventStore()
    auditor = AgentGovernanceAuditor(event_store=events)
    gate = AgentGovernanceGate(
        AgentAuthorizationEngine(policy_store(**(policy_overrides or {}))),
        auditor=auditor,
        execution_manager=execution_manager,
    )
    inner = RecordingInvoker()
    wrapper = GovernedAgentRuntimeInvoker(
        inner, gate, lambda _: principal(), auditor=auditor
    )
    return wrapper, inner, events, gate


def test_governed_invoker_projects_context_then_invokes_target():
    wrapper, inner, _, _ = governed()
    invocation = request(context=envelope())
    output = wrapper.invoke(node(), invocation)
    assert output.output == {"risk": "low"}
    assert len(inner.calls) == 1
    safe = inner.calls[0].context_envelope
    assert safe.shared_facts == {"customer_id": "A"}
    assert safe.task_context == {"goal": "assess risk"}


def test_denied_invocation_never_reaches_target_runtime():
    wrapper, inner, _, _ = governed(
        {"allowed_capabilities": frozenset({"other.capability"})}
    )
    output = wrapper.invoke(node(), request())
    assert inner.calls == []
    assert output.status.value == "denied"
    assert output.errors[0].code == "AGENT_INVOCATION_DENIED"


def test_approval_required_never_executes_until_governance_resumes():
    wrapper, inner, _, gate = governed(
        {"approval_required": True, "risk_level": "high"}
    )
    output = wrapper.invoke(node(), request())
    assert inner.calls == []
    assert output.errors[0].code == "AGENT_APPROVAL_REQUIRED"
    approval_id = output.errors[0].details_ref.removeprefix("approval://")
    assert gate.approval_adapter.records[approval_id].status == "pending"


def test_allowed_invocation_emits_complete_governance_audit_sequence():
    wrapper, _, events, _ = governed()
    wrapper.invoke(node(), request(context=envelope()))
    assert [event.event_type for event in events.query("execution-1")] == [
        "agent.authorization.checked",
        "agent.context.projected",
        "agent.invocation.started",
        "agent.invocation.completed",
        "agent.result.validated",
    ]


def test_denied_invocation_emits_checked_and_denied_events():
    wrapper, _, events, _ = governed(
        {"allowed_capabilities": frozenset({"other.capability"})}
    )
    wrapper.invoke(node(), request())
    assert [event.event_type for event in events.query()] == [
        "agent.authorization.checked", "agent.authorization.denied",
    ]


def test_result_validation_is_recorded_by_invocation_id():
    wrapper, _, _, _ = governed()
    invocation = request()
    wrapper.invoke(node(), invocation)
    assert wrapper.validations[invocation.invocation_id].trust_level is TrustLevel.VERIFIED


def test_audit_events_are_metadata_only_and_do_not_store_context_payload():
    wrapper, _, events, _ = governed()
    wrapper.invoke(node(), request(context=envelope()))
    serialized = str([event.to_dict() for event in events.query()])
    assert "customer_id" not in serialized
    assert "assess risk" not in serialized
    assert "doc-1" not in serialized


def test_trace_links_parent_target_authorization_and_projection():
    wrapper, _, events, _ = governed()
    wrapper.invoke(node(), request(context=envelope()))
    repository = InMemoryTraceRepository()
    assembler = TraceAssembler(repository)
    for event in events.query():
        assembler.consume(event)
    spans = repository.list_spans("trace-1")
    agent_span = next(span for span in spans if span.span_type == "AGENT")
    assert agent_span.parent_agent_id == "supervisor"
    assert agent_span.target_agent_id == "finance"
    assert agent_span.authorization_id
    assert agent_span.context_projection_id


def test_denied_authorization_trace_is_marked_denied():
    wrapper, _, events, _ = governed(
        {"allowed_capabilities": frozenset({"other.capability"})}
    )
    wrapper.invoke(node(), request())
    repository = InMemoryTraceRepository()
    assembler = TraceAssembler(repository)
    for event in events.query():
        assembler.consume(event)
    denied = next(
        span for span in repository.list_spans("trace-1")
        if span.name == "agent.authorization.denied"
    )
    assert denied.status == "DENIED"


def test_approval_moves_existing_execution_to_waiting_governance():
    store = InMemoryExecutionStore()
    record = ExecutionRecord(
        execution_id="execution-1", trace_id="trace-1", agent_id="supervisor",
        agent_version="1.0", artifact_id="supervisor:1.0:langgraph:a",
        artifact_hash="a" * 64, backend_type="multi_agent",
        user_id="user-1", tenant_id="tenant-1",
    )
    store.create(record)
    store.update_status("execution-1", "running")
    manager = ExecutionManager(store)
    wrapper, _, _, _ = governed(
        {"approval_required": True, "risk_level": "high"},
        execution_manager=manager,
    )
    wrapper.invoke(node(), request())
    waiting = store.get("execution-1")
    assert waiting.status is ExecutionStatus.WAITING_GOVERNANCE
    assert waiting.authorization_id


def test_execution_can_resume_after_governance_wait():
    record = ExecutionRecord(
        execution_id="execution-1", trace_id="trace-1", agent_id="supervisor",
        agent_version="1.0", artifact_id="supervisor:1.0:langgraph:a",
        artifact_hash="a" * 64, backend_type="multi_agent",
        user_id="user-1", tenant_id="tenant-1",
        status=ExecutionStatus.RUNNING,
    )
    waiting = record.transition(
        "waiting_governance", "finance", "authorization-1"
    )
    resumed = waiting.transition("running")
    assert resumed.status is ExecutionStatus.RUNNING
    assert resumed.authorization_id == "authorization-1"


def test_governance_wait_can_enter_existing_resuming_lifecycle():
    record = ExecutionRecord(
        execution_id="execution-1", trace_id="trace-1", agent_id="supervisor",
        agent_version="1.0", artifact_id="supervisor:1.0:langgraph:a",
        artifact_hash="a" * 64, backend_type="multi_agent",
        user_id="user-1", tenant_id="tenant-1", status=ExecutionStatus.RUNNING,
    )
    waiting = record.transition(
        "waiting_governance", "finance", "authorization-1"
    )
    assert waiting.transition("resuming").status is ExecutionStatus.RESUMING


def test_governance_runtime_events_flow_into_existing_audit_repository():
    wrapper, _, events, _ = governed()
    wrapper.invoke(node(), request(context=envelope()))
    repository = InMemoryAuditRepository()
    subscriber = AgentGovernanceAuditSubscriber(repository)
    for event in events.query():
        subscriber.handle(event)
    records = repository.export()
    assert len(records) == 5
    assert records[0]["event_type"] == "agent.authorization.checked"
    assert "payload" not in records[0]
