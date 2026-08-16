"""Approval engine (Phase 16.2).

Evaluates an action (type + risk) against approval policies and routes it to
human approvers.  Fail-closed: an action with no matching policy requires the
highest approver.  ``auto_approve`` policies bypass approval deterministically.
"""

from dataclasses import replace

from app.core.time import utc_now
from app.platform.business.approval.request import (
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    ApprovalRequest,
)


class ApprovalEngine:

    def __init__(self, policies=None):
        self._policies = list(policies or [])

    def policy_for(self, action_type, risk_level):
        for policy in self._policies:
            if policy.action_type == action_type and policy.risk_level == risk_level:
                return policy
        return None

    def requires_approval(self, action_type, risk_level) -> bool:
        policy = self.policy_for(action_type, risk_level)
        if policy is None:
            return True
        return (not policy.auto_approve) and bool(policy.required_approvers)

    def required_approvers(self, action_type, risk_level):
        policy = self.policy_for(action_type, risk_level)
        if policy is None:
            return ("director",)
        return policy.required_approvers

    def create_request(self, approval_id, action_id, tenant_id, requester,
                       action_type, risk_level) -> ApprovalRequest:
        status = APPROVAL_PENDING if self.requires_approval(action_type, risk_level) \
            else APPROVAL_APPROVED
        return ApprovalRequest(
            approval_id=approval_id, action_id=action_id, tenant_id=tenant_id,
            requester=requester, risk_level=risk_level, status=status,
            approved_by="auto" if status == APPROVAL_APPROVED else "",
            approved_at=utc_now() if status == APPROVAL_APPROVED else "",
        )

    def approve(self, request, approver) -> ApprovalRequest:
        return replace(request, status=APPROVAL_APPROVED, approved_by=approver,
                       approved_at=utc_now())

    def reject(self, request, approver) -> ApprovalRequest:
        return replace(request, status=APPROVAL_REJECTED, approved_by=approver,
                       approved_at=utc_now())


__all__ = ["ApprovalEngine"]
