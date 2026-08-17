"""Execution + trace public mappers (Phase 18.12)."""

from app.api.v1.schemas.executions import (
    ExecutionResponse,
    SpanResponse,
    TraceResponse,
)

# Internal ExecutionStatus -> stable public status.
_PUBLIC_STATUS = {
    "created": "CREATED",
    "running": "RUNNING",
    "waiting_approval": "WAITING_APPROVAL",
    "waiting_tool": "RUNNING",
    "waiting_governance": "WAITING",
    "completed": "COMPLETED",
    "failed": "FAILED",
    "cancelled": "CANCELLED",
    "resuming": "RUNNING",
}

_COMPONENT_LABEL = {
    "agent": "AGENT",
    "skill": "SKILL",
    "plan": "PLAN",
    "tool": "TOOL",
    "llm": "LLM",
}


def public_status(internal_status) -> str:
    value = getattr(internal_status, "value", str(internal_status))
    return _PUBLIC_STATUS.get(value, "RUNNING")


def execution_response_from(record) -> ExecutionResponse:
    return ExecutionResponse(
        execution_id=record.execution_id,
        agent_id=record.agent_id,
        agent_version=record.agent_version,
        status=public_status(record.status),
        created_at=record.created_at.isoformat(),
        completed_at=record.updated_at.isoformat() if record.status.value in
        ("completed", "failed", "cancelled") else None,
    )


def trace_response_from(trace, spans) -> TraceResponse:
    span_dtos = [
        SpanResponse(
            type=_COMPONENT_LABEL.get(getattr(s, "component", ""), "AGENT"),
            name=getattr(s, "operation", "") or getattr(s, "component", ""),
            status=("COMPLETED" if getattr(s, "status", "SUCCESS") == "SUCCESS"
                    else "FAILED"),
            duration_ms=getattr(s, "duration", 0.0),
        )
        for s in spans
    ]
    return TraceResponse(
        trace_id=trace.trace_id,
        execution_id=getattr(trace, "execution_id", ""),
        status=("COMPLETED" if trace.status == "SUCCESS" else
                "FAILED" if trace.status == "FAILED" else "RUNNING"),
        spans=span_dtos,
    )


__all__ = [
    "public_status",
    "execution_response_from",
    "trace_response_from",
]
