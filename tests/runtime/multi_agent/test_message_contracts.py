import json

import pytest

from app.runtime.backends.langgraph.state import GraphState
from app.runtime.contracts import AgentRuntimeState
from app.runtime.multi_agent import (
    AgentContextEnvelope,
    AgentContractValidationError,
    AgentContractValidator,
    AgentError,
    AgentMessage,
    AgentMessageType,
    ContextCorrelation,
    EvidenceReference,
)


def correlation():
    return ContextCorrelation(
        execution_id="execution-1",
        trace_id="trace-1",
        parent_agent_execution_id="agent-execution-sales",
        invocation_id="invocation-finance",
    )


def message(payload):
    return AgentMessage(
        execution_id="execution-1",
        agent_execution_id="agent-execution-sales",
        invocation_id="invocation-finance",
        sender_agent_id="sales_agent",
        receiver_agent_id="finance_agent",
        message_type=AgentMessageType.CONTEXT,
        payload=payload,
        trace_id="trace-1",
    )


def test_agent_message_is_transport_neutral_versioned_json():
    first = message({"customer_id": "customer-A"})
    second = message({"customer_id": "customer-A"})

    restored = AgentMessage.from_dict(json.loads(json.dumps(first.to_dict())))

    assert restored == first
    assert first.schema_version == "agent-message.v1"
    assert first.message_id != second.message_id
    assert first.message_type is AgentMessageType.CONTEXT


def test_runtime_and_langgraph_state_cannot_enter_message():
    runtime_state = AgentRuntimeState(
        task_id="task", trace_id="trace", tenant_id="tenant",
        agent_id="sales_agent", agent_version="1.0",
    )
    with pytest.raises(AgentContractValidationError, match="Runtime object"):
        message({"state": runtime_state})

    graph_state = GraphState(
        trace_id="trace", agent_id="sales_agent", _events=[]
    )
    with pytest.raises(AgentContractValidationError, match="LangGraph State"):
        message(graph_state)


@pytest.mark.parametrize(
    "field",
    [
        "permission_context", "memory_context", "memory_policy",
        "governance_decision", "api_key", "password", "token", "secret",
        "authorization", "credential",
    ],
)
def test_context_and_secret_fields_are_rejected(field):
    with pytest.raises(AgentContractValidationError, match="forbidden"):
        message({field: {"value": "must-not-cross"}})


def test_context_envelope_is_json_serializable_and_reference_oriented():
    envelope = AgentContextEnvelope(
        shared_facts={"customer_id": "customer-A"},
        upstream_results={"sales_agent": {"summary": "growing demand"}},
        evidence_refs=(
            EvidenceReference("tool_result", "tool-result-123", "crm_query"),
        ),
        task_context={"goal": "evaluate customer risk"},
        correlation=correlation(),
    )

    payload = json.loads(json.dumps(envelope.to_dict()))
    restored = AgentContextEnvelope.from_dict(payload)

    assert restored == envelope
    assert restored.evidence_refs[0].ref == "tool-result-123"
    assert "memory_context" not in payload
    assert "permission_context" not in payload


def test_contract_validator_rejects_oversized_payload():
    oversized = message({"summary": "x" * 2048})
    with pytest.raises(AgentContractValidationError, match="maximum size"):
        AgentContractValidator(max_payload_bytes=512).validate(oversized)


def test_agent_error_is_structured_and_has_no_stack_field():
    error = AgentError(
        code="TOOL_TIMEOUT", category="runtime",
        message="Tool did not complete", retryable=True,
        details_ref="trace://trace-1/error-1",
    )
    payload = error.to_dict()
    assert payload["retryable"] is True
    assert "stack" not in payload
    assert "traceback" not in payload
