"""Approval endpoints (Phase 18.12 / 18.12.5)."""

from fastapi import APIRouter, Depends, Header, Request

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


def _decision(operation, approval_id, body, request, ctx):
    gateway = request.app.state.gateway
    guard = request.app.state.idempotency_guard
    token = guard.resolve(request, ctx, operation, approval_id,
                          body.model_dump())
    if token is not None and token.prior_result is not None:
        approval = gateway.get_approval(ctx.trusted_context, approval_id)
        return approval_summary_from(approval)
    if operation == "approveRequest":
        updated = gateway.approve(ctx.trusted_context, approval_id, body.comment)
    else:
        updated = gateway.reject(ctx.trusted_context, approval_id, body.comment)
    if token is not None:
        guard.record(token, updated.status)
    return approval_summary_from(updated)


@router.post("/v1/approvals/{approval_id}/approve",
             response_model=ApprovalSummary)
def approve(approval_id: str, body: DecisionRequest, request: Request,
            idempotency_key: str | None = Header(
                None, alias="Idempotency-Key",
                description="Opaque client-generated retry key."),
            ctx: ApiRequestContext = Depends(get_api_request_context)):
    return _decision("approveRequest", approval_id, body, request, ctx)


@router.post("/v1/approvals/{approval_id}/reject",
             response_model=ApprovalSummary)
def reject(approval_id: str, body: DecisionRequest, request: Request,
           idempotency_key: str | None = Header(
               None, alias="Idempotency-Key",
               description="Opaque client-generated retry key."),
           ctx: ApiRequestContext = Depends(get_api_request_context)):
    return _decision("rejectRequest", approval_id, body, request, ctx)


__all__ = ["router"]
