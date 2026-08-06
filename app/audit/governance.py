from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass
class GovernanceAuditRecord:
    event_type: str
    operator: str
    agent_id: str
    version: str
    timestamp: str
    metadata: dict = field(default_factory=dict)
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self):
        return {
            "audit_id": self.audit_id,
            "event_type": self.event_type,
            "operator": self.operator,
            "agent_id": self.agent_id,
            "version": self.version,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class GovernanceAuditSubscriber:
    def __init__(self):
        self.records = []

    def handle(self, event):
        payload = event.to_dict() if hasattr(event, "to_dict") else dict(event)
        if "event_type" not in payload or "agent_id" not in payload or "version" not in payload:
            return None
        known = {"event_type", "operator", "agent_id", "version", "timestamp"}
        record = GovernanceAuditRecord(
            event_type=payload["event_type"], operator=payload["operator"],
            agent_id=payload["agent_id"], version=payload["version"],
            timestamp=payload.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            metadata={k: v for k, v in payload.items() if k not in known},
        )
        self.records.append(record)
        return record

    def query(self, agent_id=None, version=None, event_type=None):
        return [r for r in self.records
                if (agent_id is None or r.agent_id == agent_id)
                and (version is None or r.version == version)
                and (event_type is None or r.event_type == event_type)]

    def history(self, agent_id, version=None):
        return self.query(agent_id, version)
