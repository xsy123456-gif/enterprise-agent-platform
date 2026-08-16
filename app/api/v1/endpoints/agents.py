"""Agent endpoints (Phase 18.12)."""

import uuid

from fastapi import APIRouter, Depends, Request, Response

from app.api.dependencies.context import get_api_request_context
from app.api.context import ApiRequestContext
from app.api.errors import ApiError, ApiErrorCode
from app.api.v1.mappers.agent import agent_summary_from
from app.api.v1.schemas.agents import (
    AgentListResponse,
    ExecutionRef,
    MessageRequest,
    MessageResponse,
    ResponseBody,
)
from app.api.config import ApiConfig

router = APIRouter(tags=["Agents"])


def _config(request: Request) -> ApiConfig:
    return request.app.state.api_config


@router.get("/v1/agents", response_model=AgentListResponse)
def list_agents(request: Request,
                ctx: ApiRequestContext = Depends(get_api_request_context)):
    gateway = request.app.state.gateway
    definitions = gateway.list_agents(ctx.trusted_context)
    return AgentListResponse(
        items=[agent_summary_from(d) for d in definitions])


@router.post("/v1/agents/{agent_id}/messages",
             response_model=MessageResponse, status_code=200)
def send_message(agent_id: str, body: MessageRequest, request: Request,
                 response: Response,
                 ctx: ApiRequestContext = Depends(get_api_request_context)):
    config = _config(request)
    message = (body.message or "").strip()
    if not message:
        raise ApiError(ApiErrorCode.INVALID_REQUEST,
                       "message must not be empty.", http_status=400)
    if len(message) > config.max_message_chars:
        raise ApiError(ApiErrorCode.INVALID_REQUEST,
                       "message too long.", http_status=400)

    gateway = request.app.state.gateway
    trace_id = ctx.request_id or uuid.uuid4().hex
    agent_response = gateway.send_message(
        ctx.trusted_context, agent_id, message, body.session_id, trace_id)

    execution = None
    if agent_response.execution_id:
        execution = ExecutionRef(
            execution_id=agent_response.execution_id,
            status="COMPLETED",
            agent_id=agent_id,
            agent_version="",
        )
        response.headers["X-Execution-ID"] = agent_response.execution_id
    if agent_response.trace_id:
        response.headers["X-Trace-ID"] = agent_response.trace_id

    return MessageResponse(
        request_id=ctx.request_id,
        session_id=agent_response.session_id or body.session_id,
        execution=execution,
        response=ResponseBody(
            content=agent_response.message,
            citations=list(agent_response.citations),
        ),
        links={
            "execution": f"/v1/executions/{agent_response.execution_id}"
            if agent_response.execution_id else None,
            "trace": f"/v1/executions/{agent_response.execution_id}/trace"
            if agent_response.execution_id else None,
        },
    )


__all__ = ["router"]
