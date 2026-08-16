"""Phase 14.4 Context Protocol tests."""

import pytest

from app.platform.agent_collaboration.context import (
    AgentContextProvider,
    AgentContextEnvelope,
)
from app.platform.agent_collaboration.errors import ContextAccessDeniedError


def test_context_envelope_carries_facts_and_references():
    provider = AgentContextProvider()
    envelope = provider.create_context(
        task_id="t1", source_agent="sales_agent", target_agent="commerce_agent",
        facts={"sales_drop": "20%", "quarter": "Q3"},
        artifacts=("diag_123",), references=("user_goal",))
    assert envelope.facts["sales_drop"] == "20%"
    assert envelope.artifacts == ("diag_123",)


def test_context_rejects_forbidden_fields():
    with pytest.raises(ValueError):
        AgentContextEnvelope(
            context_id="c1", task_id="t1", source_agent="a", target_agent="b",
            facts={"permission": "admin"})
    with pytest.raises(ValueError):
        AgentContextEnvelope(
            context_id="c1", task_id="t1", source_agent="a", target_agent="b",
            facts={"credential": "tok"})


def test_context_access_control():
    provider = AgentContextProvider()
    envelope = provider.create_context(
        task_id="t1", source_agent="sales_agent", target_agent="commerce_agent",
        facts={"sales_drop": "20%"})
    # source and target may access
    assert provider.get_context(envelope.context_id, "sales_agent") == envelope
    assert provider.get_context(envelope.context_id, "commerce_agent") == envelope
    # third-party denied
    with pytest.raises(ContextAccessDeniedError):
        provider.get_context(envelope.context_id, "finance_agent")


def test_context_unknown_denied():
    provider = AgentContextProvider()
    with pytest.raises(ContextAccessDeniedError):
        provider.get_context("missing", "sales_agent")
