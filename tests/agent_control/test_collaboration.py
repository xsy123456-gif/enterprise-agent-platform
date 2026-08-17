"""Phase 13.6 Agent Collaboration Contract tests."""

import pytest

from app.platform.agent_control.collaboration import (
    AgentMessage,
    AgentMessageProtocol,
)
from app.platform.agent_control.errors import AgentValidationError


def test_message_round_trip():
    message = AgentMessage(
        message_id="m1", from_agent="sales_agent", to_agent="commerce_agent",
        task="查询商品库存", context_reference="listing_B001", trace_id="t1")
    protocol = AgentMessageProtocol()
    assert protocol.validate(message) == message


def test_message_self_reference_rejected():
    with pytest.raises(AgentValidationError):
        AgentMessageProtocol().validate(AgentMessage(
            message_id="m1", from_agent="sales_agent", to_agent="sales_agent",
            task="x"))


def test_message_requires_task():
    with pytest.raises(AgentValidationError):
        AgentMessageProtocol().validate(AgentMessage(
            message_id="m1", from_agent="sales_agent", to_agent="commerce_agent"))
