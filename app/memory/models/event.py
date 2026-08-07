from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    source_kind: str
    source_id: str
    observations: list
    metadata: dict
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = MemoryEventStatus.RECEIVED
    created_at: datetime = field(default_factory=utc_now)
    processed_at: datetime | None = None
    error: str | None = None

    @classmethod
    def from_submit_request(cls, request):
        return cls(
            trace_id=request.trace_id, task_id=request.source.source_id,
            agent_id=request.scope.agent_id, user_id=request.scope.user_id,
            tenant_id=request.scope.tenant_id, department_id=request.scope.department_id,
            source_kind=request.source.kind, source_id=request.source.source_id,
            observations=list(request.observations),
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
        return MemorySource(self.source_kind, self.source_id)

    def storage_metadata(self):
        return {
            **self.metadata,
            "_memory_event_source": {
                "kind": self.source_kind, "source_id": self.source_id,
            },
            "_memory_event_observations": [
                {"kind": item.kind, "content": item.content,
                 "source_ref": item.source_ref, "metadata": item.metadata}
                for item in self.observations
            ],
        }

    @classmethod
    def from_storage_record(cls, row):
        from app.memory.api.models import MemoryObservation
        metadata = dict(row.pop("metadata") or {})
        row.pop("event_type", None)
        row.pop("input", None)
        row.pop("output", None)
        row.pop("tool_results", None)
        source = metadata.pop("_memory_event_source", None)
        observations = metadata.pop("_memory_event_observations", None)
        if source is None or observations is None:
            raise RuntimeError("Stored Memory event is missing generic source/observations")
        return cls(
            **row,
            source_kind=source["kind"], source_id=source["source_id"],
            observations=[MemoryObservation(**item) for item in observations],
            metadata=metadata,
        )
