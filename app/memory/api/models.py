from dataclasses import dataclass, field
from typing import Any

from app.memory.models.scope import MemoryScope


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
                raise ValueError(f"{name} is required")
            object.__setattr__(self, name, value.strip())


@dataclass(frozen=True)
class MemorySource:
    kind: str
    source_id: str

    def __post_init__(self):
        if not self.kind or not self.source_id:
            raise ValueError("Memory source kind and source_id are required")


@dataclass(frozen=True)
class MemoryObservation:
    kind: str
    content: Any
    source_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


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
            raise ValueError("idempotency_key is required")
        if not self.observations:
            raise ValueError("observations are required")
        if (
            self.principal.tenant_id != self.scope.tenant_id
            or self.principal.user_id != self.scope.user_id
            or self.principal.agent_id != self.scope.agent_id
        ):
            raise ValueError("principal and scope do not describe the same subject")


@dataclass(frozen=True)
class MemoryRetrieveRequest:
    principal: MemoryPrincipal
    scope: MemoryScope
    query: str
    types: list[str] = field(default_factory=list)
    limit: int = 10
    trace_id: str = ""

    def __post_init__(self):
        if self.limit < 1:
            raise ValueError("limit must be positive")
        if (
            self.principal.tenant_id != self.scope.tenant_id
            or self.principal.user_id != self.scope.user_id
            or self.principal.agent_id != self.scope.agent_id
        ):
            raise ValueError("principal and scope do not describe the same subject")

    @property
    def tenant_id(self):
        return self.scope.tenant_id

    @property
    def user_id(self):
        return self.scope.user_id

    @property
    def agent_id(self):
        return self.scope.agent_id

    @property
    def department_id(self):
        return self.scope.department_id

    @property
    def requested_types(self):
        return self.types


@dataclass(frozen=True)
class LegacyMemoryEventRequest:
    trace_id: str
    task_id: str
    agent_id: str
    user_id: str
    tenant_id: str
    event_type: str
    input: dict[str, Any]
    output: dict[str, Any]
    tool_results: list[Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    department_id: str | None = None

    def __post_init__(self):
        if not all((self.trace_id, self.task_id, self.agent_id, self.user_id, self.tenant_id, self.event_type)):
            raise ValueError("Memory event identity and scope fields are required")

    @property
    def scope(self):
        return MemoryScope(
            tenant_id=self.tenant_id, department_id=self.department_id,
            user_id=self.user_id, agent_id=self.agent_id,
        )


# Kept as an import-only migration alias while callers move to MemorySubmitRequest.
MemoryEventRequest = LegacyMemoryEventRequest


@dataclass(frozen=True)
class MemorySubmitResponse:
    accepted: bool
    event_id: str
    status: str
