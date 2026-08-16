"""Collaboration audit (Phase 14.7).

Records collaboration operations.  Forbidden: secret / credential / raw private
context are structurally absent.
"""

from dataclasses import dataclass, field

from app.core.time import utc_now

OP_TASK_CREATED = "CollaborationTaskCreated"
OP_AGENT_DELEGATED = "AgentDelegated"
OP_CONTEXT_SHARED = "ContextShared"
OP_AGENT_COMPLETED = "AgentCompleted"
OP_AGGREGATION_COMPLETED = "AggregationCompleted"
OPERATIONS = frozenset({
    OP_TASK_CREATED, OP_AGENT_DELEGATED, OP_CONTEXT_SHARED,
    OP_AGENT_COMPLETED, OP_AGGREGATION_COMPLETED,
})


@dataclass(frozen=True)
class CollaborationAuditRecord:
    audit_id: str
    task_id: str
    agent_id: str
    operation: str
    timestamp: str = field(default_factory=utc_now)
    trace_id: str = ""

    def __post_init__(self):
        if self.operation not in OPERATIONS:
            raise ValueError(f"unknown operation: {self.operation}")

    def to_dict(self) -> dict:
        return {
            "audit_id": self.audit_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "operation": self.operation,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
        }


class CollaborationAuditLogger:

    def __init__(self):
        self.records = []

    def record(self, task_id, agent_id, operation, trace_id="") -> CollaborationAuditRecord:
        record = CollaborationAuditRecord(
            audit_id=f"{task_id}:{operation}:{len(self.records)}",
            task_id=task_id, agent_id=agent_id, operation=operation,
            trace_id=trace_id,
        )
        self.records.append(record)
        return record

    def list(self):
        return list(self.records)


__all__ = [
    "CollaborationAuditRecord",
    "CollaborationAuditLogger",
    "OP_TASK_CREATED",
    "OP_AGENT_DELEGATED",
    "OP_CONTEXT_SHARED",
    "OP_AGENT_COMPLETED",
    "OP_AGGREGATION_COMPLETED",
    "OPERATIONS",
]
