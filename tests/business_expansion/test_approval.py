"""Phase 16.2 Approval Workflow tests."""

from app.platform.business.approval import ApprovalEngine, ApprovalPolicy


def _engine():
    return ApprovalEngine([
        ApprovalPolicy(policy_id="p1", action_type="UPDATE_AD_BUDGET",
                       risk_level="LOW", auto_approve=True),
        ApprovalPolicy(policy_id="p2", action_type="UPDATE_AD_BUDGET",
                       risk_level="MEDIUM",
                       required_approvers=("marketing_manager",)),
        ApprovalPolicy(policy_id="p3", action_type="UPDATE_AD_BUDGET",
                       risk_level="HIGH", required_approvers=("director",)),
    ])


def test_auto_approve_low_risk():
    engine = _engine()
    assert engine.requires_approval("UPDATE_AD_BUDGET", "LOW") is False
    request = engine.create_request("a1", "action1", "company_A", "agent",
                                    "UPDATE_AD_BUDGET", "LOW")
    assert request.status == "APPROVED"
    assert request.approved_by == "auto"


def test_medium_risk_requires_marketing_manager():
    engine = _engine()
    assert engine.requires_approval("UPDATE_AD_BUDGET", "MEDIUM") is True
    assert engine.required_approvers("UPDATE_AD_BUDGET", "MEDIUM") == \
        ("marketing_manager",)
    request = engine.create_request("a1", "action1", "company_A", "agent",
                                    "UPDATE_AD_BUDGET", "MEDIUM")
    assert request.status == "PENDING"
    approved = engine.approve(request, "marketing_manager")
    assert approved.status == "APPROVED"


def test_high_risk_requires_director():
    engine = _engine()
    assert engine.required_approvers("UPDATE_AD_BUDGET", "HIGH") == ("director",)


def test_unknown_action_fails_closed():
    engine = _engine()
    assert engine.requires_approval("UNKNOWN_ACTION", "LOW") is True
    assert engine.required_approvers("UNKNOWN_ACTION", "LOW") == ("director",)


def test_reject():
    engine = _engine()
    request = engine.create_request("a1", "action1", "company_A", "agent",
                                    "UPDATE_AD_BUDGET", "MEDIUM")
    rejected = engine.reject(request, "marketing_manager")
    assert rejected.status == "REJECTED"
