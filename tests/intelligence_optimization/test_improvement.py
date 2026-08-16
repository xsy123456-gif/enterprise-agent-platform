"""Phase 17.3 Improvement Lifecycle tests."""

import pytest

from app.platform.intelligence.errors import ImprovementError
from app.platform.intelligence.improvement import (
    AgentImprovementRequest,
    ImprovementApproval,
    ImprovementLifecycle,
)


def _request(request_id="r1"):
    return AgentImprovementRequest(
        request_id=request_id, proposal_id="p1", target_agent="commerce_agent",
        change_type="skill_config", created_by="admin")


def test_lifecycle_full_path():
    lifecycle = ImprovementLifecycle()
    request = _request()
    lifecycle.create(request)
    lifecycle.transition("r1", "VALIDATED")
    lifecycle.transition("r1", "REVIEWING")
    lifecycle.transition("r1", "APPROVED")
    lifecycle.transition("r1", "IMPLEMENTING")
    lifecycle.transition("r1", "TESTING")
    lifecycle.transition("r1", "RELEASED")
    assert lifecycle.status("r1") == "RELEASED"


def test_lifecycle_invalid_transition():
    lifecycle = ImprovementLifecycle()
    lifecycle.create(_request())
    with pytest.raises(ImprovementError):
        lifecycle.transition("r1", "RELEASED")  # skip validation/review


def test_approval_moves_reviewing_to_approved():
    lifecycle = ImprovementLifecycle()
    request = _request()
    lifecycle.create(request)
    lifecycle.transition("r1", "VALIDATED")
    lifecycle.transition("r1", "REVIEWING")
    approval = ImprovementApproval(lifecycle)
    approved = approval.approve(request, "lead")
    assert approved.approval_status == "APPROVED"
    assert lifecycle.status("r1") == "APPROVED"


def test_approval_requires_reviewing_state():
    lifecycle = ImprovementLifecycle()
    request = _request()
    lifecycle.create(request)
    approval = ImprovementApproval(lifecycle)
    with pytest.raises(ImprovementError):
        approval.approve(request, "lead")  # not REVIEWING yet


def test_rollback_from_released():
    lifecycle = ImprovementLifecycle()
    lifecycle.create(_request())
    for state in ("VALIDATED", "REVIEWING", "APPROVED", "IMPLEMENTING",
                  "TESTING", "RELEASED"):
        lifecycle.transition("r1", state)
    lifecycle.rollback("r1")
    assert lifecycle.status("r1") == "ROLLED_BACK"
