"""Phase 14.6 Collaboration Governance tests."""

import pytest

from app.platform.agent_collaboration.errors import DelegationDeniedError
from app.platform.agent_collaboration.governance import (
    AgentCollaborationPolicy,
    CollaborationAccessControl,
)


def _control():
    return CollaborationAccessControl([
        AgentCollaborationPolicy(
            policy_id="p1", source_agent="sales_agent",
            target_agent="commerce_agent", allowed=True, max_depth=2,
            max_cost=10.0),
        AgentCollaborationPolicy(
            policy_id="p2", source_agent="finance_agent",
            target_agent="commerce_agent", allowed=False),
    ])


def test_allowed_delegation():
    control = _control()
    assert control.check("sales_agent", "commerce_agent") is True
    control.authorize("sales_agent", "commerce_agent")


def test_denied_delegation():
    control = _control()
    assert control.check("finance_agent", "commerce_agent") is False
    with pytest.raises(DelegationDeniedError):
        control.authorize("finance_agent", "commerce_agent")


def test_default_deny_without_policy():
    control = _control()
    assert control.check("marketing_agent", "commerce_agent") is False


def test_max_depth_and_cost_per_edge():
    control = _control()
    assert control.max_depth("sales_agent", "commerce_agent") == 2
    assert control.max_cost("sales_agent", "commerce_agent") == 10.0
    assert control.max_depth("unknown", "commerce_agent", default=5) == 5


def test_allowed_delegations_set():
    control = _control()
    assert ("sales_agent", "commerce_agent") in control.allowed_delegations()
    assert ("finance_agent", "commerce_agent") not in control.allowed_delegations()
