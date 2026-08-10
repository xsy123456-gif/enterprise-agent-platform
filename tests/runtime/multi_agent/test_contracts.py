import json

import pytest

from app.runtime.contracts import AgentRuntimeState
from app.runtime.multi_agent import (
    AgentContractValidationError,
    AgentExecutionResult,
    AgentExecutionStatus,
    AgentInvocationRequest,
)


def test_invocation_contract_is_serializable_and_context_is_reference_only():
    request = AgentInvocationRequest(
        execution_id="execution-1",
        parent_agent="supervisor",
        target_agent="finance_agent",
        capability="financial_analysis",
        input={"customer": "A"},
        trace_id="trace-1",
        target_artifact_id="finance:1.0:langgraph:abc",
        target_artifact_hash="a" * 64,
        context_reference="context://execution-1/sales-agent-result",
    )

    payload = json.loads(json.dumps(request.to_dict()))
    restored = AgentInvocationRequest.from_dict(payload)

    assert restored == request
    assert payload["schema_version"] == "agent-invocation.v1"
    assert "runtime_state" not in payload
    assert "permission_context" not in payload


def test_agent_runtime_state_cannot_cross_invocation_boundary():
    state = AgentRuntimeState(
        task_id="task", trace_id="trace", tenant_id="tenant",
        agent_id="sales_agent", agent_version="1.0",
    )

    with pytest.raises(AgentContractValidationError, match="Runtime object"):
        AgentInvocationRequest(
            execution_id="execution-1",
            parent_agent="supervisor",
            target_agent="finance_agent",
            capability="financial_analysis",
            input={"other_agent_state": state},
            trace_id="trace-1",
            target_artifact_id="finance:1",
            target_artifact_hash="a" * 64,
        )


def test_result_contract_is_serializable_and_does_not_expose_runtime_state():
    result = AgentExecutionResult(
        execution_id="execution-1",
        agent_execution_id="agent-execution-1",
        agent_id="finance_agent",
        agent_version="1.0",
        artifact_id="finance:1.0:langgraph:abc",
        artifact_hash="a" * 64,
        status=AgentExecutionStatus.COMPLETED,
        output={"risk": "low"},
        artifacts=({"artifact_id": "report-1", "media_type": "application/json"},),
        confidence=0.92,
        metadata={"model": "deepseek-chat"},
    )

    payload = json.loads(json.dumps(result.to_dict()))
    restored = AgentExecutionResult.from_dict(payload)

    assert restored == result
    assert restored.output == {"risk": "low"}
    assert restored.status.value == AgentExecutionStatus.COMPLETED.value
    assert "state" not in payload
    assert "permission_context" not in payload


def test_result_rejects_another_agent_runtime_state():
    state = AgentRuntimeState(
        task_id="task", trace_id="trace", tenant_id="tenant",
        agent_id="finance_agent", agent_version="1.0",
    )
    with pytest.raises(AgentContractValidationError, match="Runtime object"):
        AgentExecutionResult(
            execution_id="execution-1",
            agent_execution_id="agent-execution-1",
            agent_id="finance_agent",
            agent_version="1.0",
            artifact_id="finance:1.0:langgraph:abc",
            artifact_hash="a" * 64,
            status="completed",
            output={"state": state},
        )
