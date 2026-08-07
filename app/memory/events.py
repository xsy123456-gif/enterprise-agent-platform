from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
import uuid


@dataclass(frozen=True)
class MemoryDomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    aggregate_id: str = ""
    payload: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "event_id": self.event_id, "event_type": self.event_type,
            "aggregate_id": self.aggregate_id, "payload": dict(self.payload),
            "created_at": self.created_at.isoformat(),
        }


class MemoryEventSink(Protocol):
    def publish(self, event: MemoryDomainEvent) -> None:
        ...
