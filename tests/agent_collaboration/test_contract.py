"""Phase 14.1 Collaboration Contract tests."""

import pytest

from app.platform.agent_collaboration.domain import (
    AgentDelegationRequest,
    AgentDelegationResult,
    CollaborationTask,
    TASK_CREATED,
)
from app.platform.agent_collaboration.errors import CollaborationError
from app.platform.agent_collaboration.protocol import (
    MSG_TASK_REQUEST,
    AgentMessage,
    AgentMessageProtocol,
)


def test_collaboration_task_model():
    task = CollaborationTask(task_id="t1", root_agent_id="sales_agent",
                             goal="为什么Q3销售下降")
    assert task.status == TASK_CREATED
    assert not hasattr(task, "permission")
    assert not hasattr(task, "credential")
    assert not hasattr(task, "secret")


def test_delegation_request_and_result_round_trip():
    request = AgentDelegationRequest(
        delegation_id="d1", task_id="t1", from_agent_id="sales_agent",
        to_agent_id="commerce_agent", goal="分析商品销量下降原因")
    assert request.from_agent_id == "sales_agent"
    assert request.to_agent_id == "commerce_agent"
    result = AgentDelegationResult(
        delegation_id="d1", agent_id="commerce_agent",
        result_reference="diag_123", summary="库存不足")
    assert result.result_reference == "diag_123"


def test_message_protocol_validation():
    protocol = AgentMessageProtocol()
    message = AgentMessage(
        message_id="m1", task_id="t1", sender_agent="sales_agent",
        receiver_agent="commerce_agent", message_type=MSG_TASK_REQUEST,
        payload_reference="ctx_1")
    assert protocol.validate(message) == message


def test_message_self_reference_rejected():
    with pytest.raises(CollaborationError):
        AgentMessageProtocol().validate(AgentMessage(
            message_id="m1", task_id="t1", sender_agent="a", receiver_agent="a"))


def test_message_payload_forbids_secret_credential_permission():
    protocol = AgentMessageProtocol()
    with pytest.raises(CollaborationError):
        protocol.validate_payload({"secret": "x"})
    with pytest.raises(CollaborationError):
        protocol.validate_payload({"permission": "admin"})
    assert protocol.validate_payload({"fact": "sales down 20%"}) == \
        {"fact": "sales down 20%"}
