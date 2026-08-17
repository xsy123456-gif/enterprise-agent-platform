"""Execution + trace public schemas (Phase 18.12)."""

from app.api.v1.schemas.common import PublicModel


class ExecutionError(PublicModel):
    code: str
    message: str
    retryable: bool = False


class ExecutionResponse(PublicModel):
    execution_id: str
    agent_id: str = ""
    agent_version: str = ""
    status: str
    created_at: str | None = None
    completed_at: str | None = None
    waiting_reason: str | None = None
    error: ExecutionError | None = None


class SpanResponse(PublicModel):
    type: str
    name: str
    status: str
    duration_ms: float = 0.0


class TraceResponse(PublicModel):
    trace_id: str
    execution_id: str
    status: str
    spans: list[SpanResponse] = []


__all__ = ["ExecutionResponse", "ExecutionError", "SpanResponse", "TraceResponse"]
