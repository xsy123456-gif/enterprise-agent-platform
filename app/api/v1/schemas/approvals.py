"""Approval + workflow public schemas (Phase 18.12)."""

from app.api.v1.schemas.common import PublicModel


class ApprovalSummary(PublicModel):
    approval_id: str
    status: str
    risk_level: str = ""
    action_type: str = ""
    summary: str = ""
    created_at: str | None = None


class ApprovalListResponse(PublicModel):
    items: list[ApprovalSummary]
    next_cursor: str | None = None


class DecisionRequest(PublicModel):
    comment: str = ""


class WorkflowStepStatus(PublicModel):
    step_id: str
    type: str
    status: str


class WorkflowRunResponse(PublicModel):
    run_id: str
    workflow_id: str
    version: str = ""
    status: str
    steps: list[WorkflowStepStatus] = []
    waiting: dict | None = None


class ResumeRequest(PublicModel):
    signal: str = "CONTINUE"


__all__ = [
    "ApprovalSummary",
    "ApprovalListResponse",
    "DecisionRequest",
    "WorkflowStepStatus",
    "WorkflowRunResponse",
    "ResumeRequest",
]
