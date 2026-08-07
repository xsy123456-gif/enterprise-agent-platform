from dataclasses import dataclass, field
from typing import Any

from app.memory.errors import MemoryValidationError
from app.memory.models.scope import MemoryScope


MAX_OBSERVATIONS = 100
MAX_QUERY_LENGTH = 4096
MAX_LIMIT = 100
MIN_LIMIT = 1
MAX_IDEMPOTENCY_KEY_LENGTH = 256


@dataclass(frozen=True)
class MemoryPrincipal:
    subject_id: str
    tenant_id: str
    user_id: str
    agent_id: str

    def __post_init__(self):
        for name in ("subject_id", "tenant_id", "user_id", "agent_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise MemoryValidationError(f"{name} is required")
            object.__setattr__(self, name, value.strip())


@dataclass(frozen=True)
class MemorySource:
    kind: str
    source_id: str

    def __post_init__(self):
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise MemoryValidationError("Memory source kind is required")
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise MemoryValidationError("Memory source source_id is required")


@dataclass(frozen=True)
class MemoryObservation:
    kind: str
    content: Any
    source_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise MemoryValidationError("Memory observation kind is required")
        if not isinstance(self.metadata, dict):
            raise MemoryValidationError("Memory observation metadata must be a dict")


@dataclass(frozen=True)
class MemorySubmitRequest:
    principal: MemoryPrincipal
    scope: MemoryScope
    idempotency_key: str
    source: MemorySource
    observations: list[MemoryObservation]
    trace_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.idempotency_key:
            raise MemoryValidationError("idempotency_key is required")
        if len(self.idempotency_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
            raise MemoryValidationError(
                f"idempotency_key exceeds max length of {MAX_IDEMPOTENCY_KEY_LENGTH}"
            )
        if not self.observations:
            raise MemoryValidationError("observations are required")
        if len(self.observations) > MAX_OBSERVATIONS:
            raise MemoryValidationError(
                f"observations exceeds max of {MAX_OBSERVATIONS}"
            )
        if (
            self.principal.tenant_id != self.scope.tenant_id
            or self.principal.user_id != self.scope.user_id
            or self.principal.agent_id != self.scope.agent_id
        ):
            raise MemoryValidationError("principal and scope do not describe the same subject")


@dataclass(frozen=True)
class MemoryRetrieveRequest:
    principal: MemoryPrincipal
    scope: MemoryScope
    query: str
    types: list[str] = field(default_factory=list)
    limit: int = 10
    trace_id: str = ""

    def __post_init__(self):
        if len(self.query) > MAX_QUERY_LENGTH:
            raise MemoryValidationError(f"query exceeds max length of {MAX_QUERY_LENGTH}")
        if self.limit < MIN_LIMIT or self.limit > MAX_LIMIT:
            raise MemoryValidationError(f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}")
        if (
            self.principal.tenant_id != self.scope.tenant_id
            or self.principal.user_id != self.scope.user_id
            or self.principal.agent_id != self.scope.agent_id
        ):
            raise MemoryValidationError("principal and scope do not describe the same subject")
        deduped = list(dict.fromkeys(self.types))
        if len(deduped) != len(self.types):
            object.__setattr__(self, "types", deduped)

    @property
    def requested_types(self):
        return self.types


@dataclass(frozen=True)
class MemorySubmitResponse:
    accepted: bool
    event_id: str
    status: str


# ── Public API aliases (Group 3) ─────────────────────────────────

# Write
MemoryWriteRequest = MemorySubmitRequest
MemoryWriteReceipt = MemorySubmitResponse

# Read
MemoryReadRequest = MemoryRetrieveRequest

