from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from app.memory.models.scope import MemoryScope


def utc_now():
    return datetime.now(timezone.utc)


class MemoryEventStatus:
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


@dataclass
class MemoryEvent:
    trace_id: str
    task_id: str
    agent_id: str
    user_id: str
    tenant_id: str
    department_id: str | None
    event_type: str
    input: dict[str, Any]
    output: dict[str, Any]
    tool_results: list[Any]
    metadata: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = MemoryEventStatus.RECEIVED
    created_at: datetime = field(default_factory=utc_now)
    processed_at: datetime | None = None
    error: str | None = None

    @classmethod
    def from_submit_request(cls, request):
        input_data = {}
        output_data = {}
        tool_results = []
        for observation in request.observations:
            if observation.kind == "user_input":
                input_data = observation.content if isinstance(observation.content, dict) else {"content": observation.content}
            elif observation.kind == "assistant_output":
                output_data = observation.content if isinstance(observation.content, dict) else {"result": observation.content}
            elif observation.kind == "tool_result":
                tool_results.append(observation.content)
        return cls(
            trace_id=request.trace_id, task_id=request.source.source_id,
            agent_id=request.scope.agent_id, user_id=request.scope.user_id,
            tenant_id=request.scope.tenant_id, department_id=request.scope.department_id,
            event_type=request.source.kind, input=input_data, output=output_data,
            tool_results=tool_results,
            metadata={**request.metadata, "idempotency_key": request.idempotency_key,
                      "principal_subject_id": request.principal.subject_id},
        )

    @property
    def scope(self):
        return MemoryScope(
            tenant_id=self.tenant_id, department_id=self.department_id,
            user_id=self.user_id, agent_id=self.agent_id,
        )

    @property
    def principal(self):
        from app.memory.api.models import MemoryPrincipal
        return MemoryPrincipal(
            subject_id=self.metadata.get("principal_subject_id", self.user_id),
            tenant_id=self.tenant_id, user_id=self.user_id, agent_id=self.agent_id,
        )

    @property
    def source(self):
        from app.memory.api.models import MemorySource
        return MemorySource(self.event_type, self.task_id)


@dataclass(frozen=True)
class MemoryDomainEvent:
    event_type: str
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self):
        return {
            "event_type": self.event_type,
            **self.payload,
            "timestamp": self.created_at.isoformat(),
        }
