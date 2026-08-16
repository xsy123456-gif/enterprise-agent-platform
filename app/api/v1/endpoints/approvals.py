"""Approval endpoints (Phase 18.12)."""

from fastapi import APIRouter, Depends, Request

from app.api.dependencies.context import get_api_request_context
from app.api.context import ApiRequestContext
from app.api.v1.mappers.approval import approval_summary_from
from app.api.v1.schemas.approvals import (
    ApprovalListResponse,
    ApprovalSummary,
    DecisionRequest,
)

router = APIRouter(tags=["Approvals"])


@router.get("/v1/approvals", response_model=ApprovalListResponse)
def list_approvals(request: Request, status: str | None = None,
                   ctx: ApiRequestContext = Depends(get_api_request_context)):
    gateway = request.app.state.gateway
    approvals = gateway.list_approvals(ctx.trusted_context, status=status)
    return ApprovalListResponse(
        items=[approval_summary_from(a) for a in approvals])


@router.post("/v1/approvals/{approval_id}/approve",
             response_model=ApprovalSummary)
def approve(approval_id: str, body: DecisionRequest, request: Request,
            ctx: ApiRequestContext = Depends(get_api_request_context)):
    gateway = request.app.state.gateway
    updated = gateway.approve(ctx.trusted_context, approval_id, body.comment)
    return approval_summary_from(updated)


@router.post("/v1/approvals/{approval_id}/reject",
             response_model=ApprovalSummary)
def reject(approval_id: str, body: DecisionRequest, request: Request,
           ctx: ApiRequestContext = Depends(get_api_request_context)):
    gateway = request.app.state.gateway
    updated = gateway.reject(ctx.trusted_context, approval_id, body.comment)
    return approval_summary_from(updated)


__all__ = ["router"]
