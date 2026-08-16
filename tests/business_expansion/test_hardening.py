"""Phase 16.7 Hardening + Enterprise Business E2E."""

import pytest

from app.platform.business.action import ActionProposal, BusinessActionRuntime
from app.platform.business.approval import ApprovalEngine, ApprovalPolicy
from app.platform.business.audit import (
    BusinessAuditLogger,
    OP_APPROVED,
    OP_EXECUTED,
)
from app.platform.business.errors import (
    ActionExecutionError,
    ApprovalRequiredError,
)
from app.platform.business.workflow import (
    BusinessWorkflow,
    WorkflowEngine,
    WorkflowStep,
)


def _approval_engine():
    return ApprovalEngine([
        ApprovalPolicy(policy_id="p1", action_type="CREATE_PURCHASE_ORDER",
                       risk_level="LOW", auto_approve=True),
        ApprovalPolicy(policy_id="p2", action_type="CREATE_PURCHASE_ORDER",
                       risk_level="HIGH", required_approvers=("supply_director",)),
        ApprovalPolicy(policy_id="p3", action_type="UPDATE_AD_BUDGET",
                       risk_level="LOW", auto_approve=True),
    ])


# ── Enterprise Business E2E ────────────────────────────────

def test_enterprise_business_e2e_replenishment():
    audit = BusinessAuditLogger()
    action_audit = []

    class _ActionAudit:
        def record(self, action_id, operation, detail):
            action_audit.append((action_id, operation, detail))

    approval = _approval_engine()
    action_runtime = BusinessActionRuntime(
        approval_engine=approval, action_handler=lambda a, c: None,
        audit=_ActionAudit())

    def diagnose(step, ctx):
        return {"summary": "库存不足，建议补货"}

    def approve_step(step, ctx):
        proposal = ActionProposal(
            proposal_id="p1", agent_id="commerce_agent",
            recommendation="补货建议", action_type="CREATE_PURCHASE_ORDER",
            target="sku_1", risk_level="HIGH")
        action = action_runtime.create_action(proposal)
        assert action.status == "WAITING_APPROVAL"
        audit.record("company_A", "commerce_agent", "ApprovalRequested",
                     action_id=action.action_id)
        ctx["action"] = action
        return {"waiting": True}

    def create_po(step, ctx):
        action = ctx["action"]
        approved = action_runtime.approve(action, "supply_director")
        audit.record("company_A", "supply_director", "Approved",
                     action_id=approved.action_id)
        result = action_runtime.execute(approved)
        return {"result": result.status}

    def notify(step, ctx):
        return {"notified": "supply_chain"}

    handlers = {
        "AGENT_TASK": diagnose,
        "APPROVAL": approve_step,
        "ACTION": create_po,
        "NOTIFICATION": notify,
    }
    workflow = BusinessWorkflow(
        workflow_id="inventory_replenishment", version="1.0",
        steps=[
            WorkflowStep(step_id="s1", step_type="AGENT_TASK"),
            WorkflowStep(step_id="s2", step_type="APPROVAL", next_steps=("s3",)),
            WorkflowStep(step_id="s3", step_type="ACTION", next_steps=("s4",)),
            WorkflowStep(step_id="s4", step_type="NOTIFICATION"),
        ],
    )
    result = WorkflowEngine(handlers).run(workflow, context={})
    assert result.status == "COMPLETED"
    assert result.step_results["s3"]["result"] == "SUCCEEDED"
    assert result.step_results["s4"]["notified"] == "supply_chain"
    ops = {r.operation for r in audit.list()}
    assert "ApprovalRequested" in ops
    assert "Approved" in ops
    assert any(op == "Executed" for _, op, _ in action_audit)


# ── Security hardening ─────────────────────────────────────

def test_approval_bypass_blocked():
    runtime = BusinessActionRuntime(approval_engine=_approval_engine())
    proposal = ActionProposal(
        proposal_id="p1", agent_id="commerce_agent",
        action_type="CREATE_PURCHASE_ORDER", target="sku_1", risk_level="HIGH")
    action = runtime.create_action(proposal)
    with pytest.raises(ApprovalRequiredError):
        runtime.execute(action)  # WAITING_APPROVAL -> blocked


def test_permission_bypass_blocked():
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


def test_workflow_injection_blocked():
    # cycle in workflow steps is rejected, never executed
    workflow = BusinessWorkflow(
        workflow_id="w", version="1.0",
        steps=[
            WorkflowStep(step_id="a", step_type="ACTION", next_steps=("b",)),
            WorkflowStep(step_id="b", step_type="ACTION", next_steps=("a",)),
        ])
    from app.platform.business.errors import WorkflowError
    with pytest.raises(WorkflowError):
        WorkflowEngine({"ACTION": lambda s, c: None}).run(workflow)


# ── Audit / replay ─────────────────────────────────────────

def test_audit_never_contains_secret():
    audit = BusinessAuditLogger()
    record = audit.record("company_A", "commerce_agent", "Executed",
                          action_id="a1", trace_id="t1")
    for forbidden in ("secret", "credential", "token", "password", "private"):
        assert forbidden not in record.to_dict()
        assert not hasattr(record, forbidden)


def test_replay_captures_action_trace():
    audit = BusinessAuditLogger()
    action = audit.record("company_A", "commerce_agent", "Executed",
                          action_id="a1", trace_id="t1")
    # replay requires action_id + trace_id + timestamp
    assert action.action_id == "a1"
    assert action.trace_id == "t1"
    assert action.timestamp
