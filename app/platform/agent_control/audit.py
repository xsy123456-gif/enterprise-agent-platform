"""Agent audit (Phase 13.8).

Records control-plane operations (created / published / executed / disabled /
deprecated) with actor + trace.  Forbidden fields: secret / credential /
private data are structurally absent.
"""

from dataclasses import dataclass, field

from app.core.time import utc_now

OP_CREATED = "created"
OP_PUBLISHED = "published"
OP_EXECUTED = "executed"
OP_DISABLED = "disabled"
OP_DEPRECATED = "deprecated"
OPERATIONS = frozenset({
    OP_CREATED, OP_PUBLISHED, OP_EXECUTED, OP_DISABLED, OP_DEPRECATED,
})


@dataclass(frozen=True)
class AgentAuditRecord:
    audit_id: str
    agent_id: str
    version: str
    actor: str
    operation: str
    timestamp: str = field(default_factory=utc_now)
    trace_id: str = ""

    def __post_init__(self):
        if self.operation not in OPERATIONS:
            raise ValueError(f"unknown operation: {self.operation}")

    def to_dict(self) -> dict:
        return {
            "audit_id": self.audit_id,
            "agent_id": self.agent_id,
            "version": self.version,
            "actor": self.actor,
            "operation": self.operation,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
        }


class AgentAuditLogger:

    def __init__(self):
        self.records = []

    def record(self, agent_id, version, actor, operation, trace_id="") -> AgentAuditRecord:
        record = AgentAuditRecord(
            audit_id=f"{agent_id}:{operation}:{self._next()}",
            agent_id=agent_id, version=version, actor=actor,
            operation=operation, trace_id=trace_id,
        )
        self.records.append(record)
        return record

    def list(self):
        return list(self.records)

    def _next(self):
        return len(self.records)


__all__ = [
    "AgentAuditRecord",
    "AgentAuditLogger",
    "OP_CREATED",
    "OP_PUBLISHED",
    "OP_EXECUTED",
    "OP_DISABLED",
    "OP_DEPRECATED",
    "OPERATIONS",
]
