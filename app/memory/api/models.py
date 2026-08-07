from dataclasses import dataclass, field
from typing import Any

from app.memory.models.scope import MemoryScope


@dataclass(frozen=True)
class MemoryRetrieveRequest:
    user_id: str
    agent_id: str
    tenant_id: str
    query: str
    types: list[str] = field(default_factory=list)
    limit: int = 10
    trace_id: str = ""
    department_id: str | None = None

    def __post_init__(self):
        if not self.user_id or not self.agent_id or not self.tenant_id:
            raise ValueError("user_id, agent_id and tenant_id are required")
        if self.limit < 1:
            raise ValueError("limit must be positive")

    @property
    def scope(self):
        return MemoryScope(
            tenant_id=self.tenant_id, department_id=self.department_id,
            user_id=self.user_id, agent_id=self.agent_id,
        )


@dataclass(frozen=True)
class MemoryEventRequest:
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


@dataclass(frozen=True)
class MemorySubmitResponse:
    accepted: bool
    event_id: str
    status: str
