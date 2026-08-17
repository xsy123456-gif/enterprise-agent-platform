"""Execution + trace endpoints (Phase 18.12)."""

from fastapi import APIRouter, Depends, Request

from app.api.dependencies.context import get_api_request_context
from app.api.context import ApiRequestContext
from app.api.v1.mappers.execution import (
    execution_response_from,
    trace_response_from,
)
from app.api.v1.schemas.executions import ExecutionResponse, TraceResponse

router = APIRouter(tags=["Executions"])


@router.get("/v1/executions/{execution_id}",
            response_model=ExecutionResponse)
def get_execution(execution_id: str, request: Request,
                  ctx: ApiRequestContext = Depends(get_api_request_context)):
    gateway = request.app.state.gateway
    record = gateway.get_execution(ctx.trusted_context, execution_id)
    return execution_response_from(record)


@router.get("/v1/executions/{execution_id}/trace",
            response_model=TraceResponse)
def get_execution_trace(execution_id: str, request: Request,
                        ctx: ApiRequestContext = Depends(get_api_request_context)):
    gateway = request.app.state.gateway
    trace, spans = gateway.get_execution_trace(ctx.trusted_context, execution_id)
    return trace_response_from(trace, spans)


__all__ = ["router"]
