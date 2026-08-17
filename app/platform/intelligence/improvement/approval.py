"""Improvement approval (Phase 17.3).

Human approval moves a REVIEWING improvement request to APPROVED (via the
lifecycle).  No autonomous self-approval.
"""

from dataclasses import replace

from app.platform.intelligence.improvement.lifecycle import (
    IMPROVEMENT_APPROVED,
    IMPROVEMENT_REVIEWING,
    ImprovementLifecycle,
)


class ImprovementApproval:

    def __init__(self, lifecycle):
        self.lifecycle = lifecycle
        self.decisions = []

    def approve(self, request, approver):
        if self.lifecycle.status(request.request_id) != IMPROVEMENT_REVIEWING:
            from app.platform.intelligence.errors import ImprovementError
            raise ImprovementError(
                f"request {request.request_id!r} is not REVIEWING"
            )
        self.lifecycle.transition(request.request_id, IMPROVEMENT_APPROVED)
        self.decisions.append((request.request_id, approver, "APPROVED"))
        return replace(request, approval_status="APPROVED")

    def reject(self, request, approver):
        self.decisions.append((request.request_id, approver, "REJECTED"))
        return replace(request, approval_status="REJECTED")


__all__ = ["ImprovementApproval"]
