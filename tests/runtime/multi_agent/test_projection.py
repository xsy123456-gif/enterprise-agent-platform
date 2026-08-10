import pytest

from app.runtime.contracts import AgentRuntimeState, ExecutionResult
from app.runtime.multi_agent import (
    AgentExecutionResult,
    AgentInvocationRequest,
    AgentNode,
    AgentResultMapper,
    AgentResultStatus,
    ContextProjector,
    ContextTransferPolicy,
    EvidenceReference,
)


def setup_contracts():
    node = AgentNode(
        agent_id="finance_agent",
        artifact_id="finance_agent:1.0:langgraph:abc123",
        artifact_hash="a" * 64,
        capability="financial_analysis",
    )
    request = AgentInvocationRequest(
        execution_id="execution-1", parent_agent="supervisor",
        target_agent="finance_agent", capability="financial_analysis",
        input={"customer": "A"}, trace_id="trace-1",
        target_artifact_id=node.artifact_id,
        target_artifact_hash=node.artifact_hash,
    )
    state = AgentRuntimeState(
        task_id="execution-1", trace_id="trace-1", tenant_id="tenant",
        agent_id="finance_agent", agent_version="1.0", response="risk low",
    )
    runtime_result = ExecutionResult(
        task_id="execution-1", status="completed", response="risk low", state=state,
    )
    return node, request, runtime_result


def test_result_mapper_exposes_business_result_not_runtime_state():
    node, request, runtime_result = setup_contracts()
    result = AgentResultMapper().map(runtime_result, request, node)

    assert result.status is AgentResultStatus.COMPLETED
    assert result.output == {"response": "risk low"}
    assert result.artifact_hash == "a" * 64
    assert result.provenance.source_agent_id == "finance_agent"
    assert "state" not in result.to_dict()


def test_result_mapper_normalizes_exception_without_raw_stack_or_message():
    node, request, _ = setup_contracts()
    result = AgentResultMapper().map_error(
        RuntimeError("database password=secret\nTraceback: private"),
        request, node,
    )

    assert result.status is AgentResultStatus.FAILED
    assert result.errors[0].code == "RUNTIME_ERROR"
    assert result.errors[0].message == "Agent Runtime execution failed"
    assert "secret" not in str(result.to_dict())
    assert "Traceback" not in str(result.to_dict())


def test_context_projector_sanitizes_context_and_preserves_provenance():
    node, request, runtime_result = setup_contracts()
    result = AgentResultMapper().map(runtime_result, request, node)
    projected = ContextProjector(
        ContextTransferPolicy(allowed_shared_fields=frozenset({"customer_id"}))
    ).project(
        result,
        trace_id=request.trace_id,
        invocation_id=request.invocation_id,
        source_message_id="message-1",
        shared_facts={
            "customer_id": "A", "unapproved": "dropped",
            "permission_context": {"crm.read": True},
        },
        task_context={"goal": "evaluate risk", "memory_policy": "private"},
    )

    assert projected.shared_facts == {"customer_id": "A"}
    assert projected.task_context == {"goal": "evaluate risk"}
    assert projected.provenance[0].source_artifact_hash == "a" * 64
    assert projected.provenance[0].source_message_id == "message-1"
    assert projected.correlation.source_message_id == "message-1"


def test_context_projector_rejects_sensitive_shared_fact():
    node, request, runtime_result = setup_contracts()
    result = AgentResultMapper().map(runtime_result, request, node)
    with pytest.raises(ValueError, match="Sensitive context field"):
        ContextProjector().project(
            result, trace_id="trace-1", invocation_id=request.invocation_id,
            shared_facts={"api_key": "secret"},
        )
