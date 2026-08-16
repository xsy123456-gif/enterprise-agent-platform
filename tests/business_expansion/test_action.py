"""Phase 16.3 Action Runtime tests."""

import pytest

from app.platform.business.action import ActionProposal, BusinessActionRuntime
from app.platform.business.approval import ApprovalEngine, ApprovalPolicy
from app.platform.business.errors import (
    ActionExecutionError,
    ApprovalRequiredError,
)


def _approval_engine():
    return ApprovalEngine([
        ApprovalPolicy(policy_id="p1", action_type="UPDATE_AD_BUDGET",
                       risk_level="LOW", auto_approve=True),
        ApprovalPolicy(policy_id="p2", action_type="UPDATE_AD_BUDGET",
                       risk_level="HIGH", required_approvers=("director",)),
    ])


class _Audit:
    def __init__(self):
        self.records = []

    def record(self, action_id, operation, detail):
        self.records.append((action_id, operation, detail))


def test_agent_only_proposes_runtime_executes():
    proposal = ActionProposal(
        proposal_id="p1", agent_id="commerce_agent",
        recommendation="降低 Campaign A 预算 20%", action_type="UPDATE_AD_BUDGET",
        target="campaign_A", risk_level="LOW",
        parameters={"value": "-20%"})
    # the proposal is a recommendation, not an execution
    assert proposal.action_type == "UPDATE_AD_BUDGET"
    assert not hasattr(proposal, "execute")


def test_low_risk_action_auto_approved_and_executed():
    runtime = BusinessActionRuntime(approval_engine=_approval_engine(),
                                    action_handler=lambda a, c: None,
                                    audit=_Audit())
    proposal = ActionProposal(
        proposal_id="p1", agent_id="commerce_agent",
        action_type="UPDATE_AD_BUDGET", target="campaign_A", risk_level="LOW")
    action = runtime.create_action(proposal)
    assert action.status == "APPROVED"
    result = runtime.execute(action)
    assert result.status == "SUCCEEDED"


def test_high_risk_action_requires_approval():
    runtime = BusinessActionRuntime(approval_engine=_approval_engine(),
                                    action_handler=lambda a, c: None)
    proposal = ActionProposal(
        proposal_id="p1", agent_id="commerce_agent",
        action_type="UPDATE_AD_BUDGET", target="campaign_A", risk_level="HIGH")
    action = runtime.create_action(proposal)
    assert action.status == "WAITING_APPROVAL"
    with pytest.raises(ApprovalRequiredError):
        runtime.execute(action)
    approved = runtime.approve(action, "director")
    assert approved.status == "APPROVED"
    result = runtime.execute(approved)
    assert result.status == "SUCCEEDED"


def test_permission_denied_blocks_execution():
    runtime = BusinessActionRuntime(
        approval_engine=_approval_engine(),
        permission_checker=lambda a: False,
        action_handler=lambda a, c: None)
    proposal = ActionProposal(
        proposal_id="p1", agent_id="commerce_agent",
        action_type="UPDATE_AD_BUDGET", target="campaign_A", risk_level="LOW")
    action = runtime.create_action(proposal)
    with pytest.raises(ActionExecutionError):
        runtime.execute(action)


def test_execution_failure_recorded_in_audit():
    audit = _Audit()

    def handler(action, context):
        raise RuntimeError("amazon api down")

    runtime = BusinessActionRuntime(approval_engine=_approval_engine(),
                                    action_handler=handler, audit=audit)
    proposal = ActionProposal(
        proposal_id="p1", agent_id="commerce_agent",
        action_type="UPDATE_AD_BUDGET", target="campaign_A", risk_level="LOW")
    action = runtime.create_action(proposal)
    with pytest.raises(ActionExecutionError):
        runtime.execute(action)
    assert any(op == "Failed" for _, op, _ in audit.records)
