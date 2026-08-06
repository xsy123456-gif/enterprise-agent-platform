from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass(frozen=True)
class MemoryAuditRecord:
    event_type: str
    payload: dict
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MemoryAuditSubscriber:
    def __init__(self):
        self.records = []

    def handle(self, event):
        if not getattr(event, "event_type", "").startswith("memory."):
            return None
        record = MemoryAuditRecord(event.event_type, dict(event.payload))
        self.records.append(record)
        return record

    def query(self, event_type=None, agent_id=None):
        return [record for record in self.records
                if (event_type is None or record.event_type == event_type)
                and (agent_id is None or record.payload.get("agent_id") == agent_id)]
