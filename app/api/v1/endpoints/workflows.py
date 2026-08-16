"""Workflow run endpoints (Phase 18.12)."""

from fastapi import APIRouter, Depends, Header, Request

from app.api.dependencies.context import get_api_request_context
from app.api.context import ApiRequestContext
from app.api.v1.mappers.approval import workflow_run_response_from
from app.api.v1.schemas.workflows import ResumeRequest, WorkflowRunResponse

router = APIRouter(tags=["Workflows"])


@router.get("/v1/workflow-runs/{run_id}", response_model=WorkflowRunResponse)
def get_workflow_run(run_id: str, request: Request,
                     ctx: ApiRequestContext = Depends(get_api_request_context)):
    gateway = request.app.state.gateway
    run = gateway.get_workflow_run(ctx.trusted_context, run_id)
    return workflow_run_response_from(run)


@router.post("/v1/workflow-runs/{run_id}/resume",
             response_model=WorkflowRunResponse)
def resume_workflow(run_id: str, body: ResumeRequest, request: Request,
                    idempotency_key: str | None = Header(
                        None, alias="Idempotency-Key",
                        description="Opaque client-generated retry key."),
                    ctx: ApiRequestContext = Depends(get_api_request_context)):
    gateway = request.app.state.gateway
    guard = request.app.state.idempotency_guard
    token = guard.resolve(request, ctx, "resumeWorkflow", run_id,
                          body.model_dump())
    if token is not None and token.prior_result is not None:
        run = gateway.get_workflow_run(ctx.trusted_context, run_id)
        return workflow_run_response_from(run)
    run = gateway.resume_workflow(ctx.trusted_context, run_id, body.signal)
    if token is not None:
        guard.record(token, run.run_id)
    return workflow_run_response_from(run)


__all__ = ["router"]
