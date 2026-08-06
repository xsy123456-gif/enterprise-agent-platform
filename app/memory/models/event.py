from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


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
