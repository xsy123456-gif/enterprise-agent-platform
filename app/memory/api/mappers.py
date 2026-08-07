"""Public ↔ Internal mappers for Group 3 boundary.

Converts:
  MemoryWriteRequest   → MemorySubmitRequest (internal)
  MemoryWriteReceipt   ← MemorySubmitResponse (internal)
  MemoryReadRequest    → MemoryRetrieveRequest (internal)
  MemoryReadResult     ← MemoryContext (internal)
  MemoryRecord         ← MemoryReference (internal)
"""

from app.memory.api.models import (
    MemoryObservation,
    MemoryRetrieveRequest,
    MemorySource,
    MemorySubmitRequest,
    MemorySubmitResponse,
)
from app.memory.api.public_models import (
    MemoryReadRequest,
    MemoryReadResult,
    MemoryRecord,
    MemoryWriteReceipt,
    MemoryWriteRequest,
)


def to_submit_request(request: MemoryWriteRequest) -> MemorySubmitRequest:
    return MemorySubmitRequest(
        principal=request.principal,
        scope=request.scope,
        idempotency_key=request.idempotency_key,
        source=request.source,
        observations=list(request.observations),
        trace_id=request.trace_id,
        metadata=dict(request.metadata),
    )


def to_retrieve_request(request: MemoryReadRequest) -> MemoryRetrieveRequest:
    return MemoryRetrieveRequest(
        principal=request.principal,
        scope=request.scope,
        query=request.query,
        types=list(request.types),
        limit=request.limit,
        trace_id=request.trace_id,
    )


def from_submit_response(response: MemorySubmitResponse) -> MemoryWriteReceipt:
    return MemoryWriteReceipt(
        event_id=response.event_id,
        accepted=response.accepted,
        status=response.status,
    )


def from_context(context) -> MemoryReadResult:
    records = [
        MemoryRecord(
            memory_id=ref.memory_id,
            type=ref.type,
            entity_id=ref.entity_id or None,
            attribute=ref.attribute or None,
            content=ref.content,
            confidence=ref.confidence,
            importance=ref.importance,
            relevance_score=ref.relevance_score,
            created_at=ref.created_at,
        )
        for ref in context.references
    ]
    return MemoryReadResult(
        records=records,
        summary=context.summary if context.summary else None,
    )
