"""Group 3 — truly independent Public API DTOs with typed fields.

All Public Boundary validation raises MemoryValidationError.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.memory.api.models import MemoryObservation, MemoryPrincipal, MemorySource
from app.memory.api.type_registry import MemoryType, validate_type
from app.memory.errors import MemoryValidationError
from app.memory.models.scope import MemoryScope

MAX_OBSERVATIONS = 100
MAX_QUERY_LENGTH = 4096
MAX_LIMIT = 100
MIN_LIMIT = 1
MAX_IDEMPOTENCY_KEY_LENGTH = 256


@dataclass(frozen=True)
class MemoryWriteRequest:
    principal: MemoryPrincipal
    scope: MemoryScope
    idempotency_key: str
    source: MemorySource
    observations: list[MemoryObservation]
    trace_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.principal, MemoryPrincipal):
            raise MemoryValidationError("principal must be MemoryPrincipal")
        if not isinstance(self.scope, MemoryScope):
            raise MemoryValidationError("scope must be MemoryScope")
        if not isinstance(self.source, MemorySource):
            raise MemoryValidationError("source must be MemorySource")
        if not self.idempotency_key or not self.idempotency_key.strip():
            raise MemoryValidationError("idempotency_key is required")
        if len(self.idempotency_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
            raise MemoryValidationError(
                f"idempotency_key exceeds max length of {MAX_IDEMPOTENCY_KEY_LENGTH}"
            )
        if not self.observations:
            raise MemoryValidationError("observations are required")
        if len(self.observations) > MAX_OBSERVATIONS:
            raise MemoryValidationError(f"observations exceeds max of {MAX_OBSERVATIONS}")
        for obs in self.observations:
            if not isinstance(obs, MemoryObservation):
                raise MemoryValidationError("each observation must be MemoryObservation")
            if not getattr(obs, "kind", "").strip():
                raise MemoryValidationError("observation.kind is required")
            if getattr(obs, "content", None) is None:
                raise MemoryValidationError("observation.content must not be None")


@dataclass(frozen=True)
class MemoryWriteReceipt:
    event_id: str
    accepted: bool = True
    status: str = "received"


@dataclass(frozen=True)
class MemoryReadRequest:
    principal: MemoryPrincipal
    scope: MemoryScope
    query: str
    types: list[str] = field(default_factory=list)
    limit: int = 10
    trace_id: str = ""

    def __post_init__(self):
        if not isinstance(self.principal, MemoryPrincipal):
            raise MemoryValidationError("principal must be MemoryPrincipal")
        if not isinstance(self.scope, MemoryScope):
            raise MemoryValidationError("scope must be MemoryScope")
        if not self.query or not self.query.strip():
            raise MemoryValidationError("query must be non-empty")
        if len(self.query) > MAX_QUERY_LENGTH:
            raise MemoryValidationError(f"query exceeds max length of {MAX_QUERY_LENGTH}")
        if self.limit < MIN_LIMIT or self.limit > MAX_LIMIT:
            raise MemoryValidationError(f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}")
        deduped = list(dict.fromkeys(self.types))
        if len(deduped) != len(self.types):
            object.__setattr__(self, "types", deduped)
        for t in self.types:
            try:
                validate_type(t)
            except ValueError as e:
                raise MemoryValidationError(str(e)) from e


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    type: str
    entity_id: str | None = None
    attribute: str | None = None
    content: Any = None
    confidence: float = 0.0
    importance: float = 0.0
    relevance_score: float | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class MemoryReadResult:
    records: list[MemoryRecord] = field(default_factory=list)
    summary: str | None = None
