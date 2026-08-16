"""Business audit (Phase 16.7).

Records action lifecycle operations.  Forbidden: secret / credential / raw
private data are structurally absent.
"""

from dataclasses import dataclass, field

from app.core.time import utc_now

OP_ACTION_CREATED = "ActionCreated"
OP_APPROVAL_REQUESTED = "ApprovalRequested"
OP_APPROVED = "Approved"
OP_EXECUTED = "Executed"
OP_FAILED = "Failed"
OP_ROLLBACK = "Rollback"
OPERATIONS = frozenset({
    OP_ACTION_CREATED, OP_APPROVAL_REQUESTED, OP_APPROVED, OP_EXECUTED,
    OP_FAILED, OP_ROLLBACK,
})


@dataclass(frozen=True)
class BusinessAuditRecord:
    audit_id: str
    tenant_id: str
    agent_id: str
    operation: str
    action_id: str = ""
    timestamp: str = field(default_factory=utc_now)
    trace_id: str = ""
    detail: str = ""

    def __post_init__(self):
        if self.operation not in OPERATIONS:
            raise ValueError(f"unknown operation: {self.operation}")

    def to_dict(self) -> dict:
        return {
            "audit_id": self.audit_id,
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "operation": self.operation,
            "action_id": self.action_id,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "detail": self.detail,
        }


class BusinessAuditLogger:

    def __init__(self):
        self.records = []

    def record(self, tenant_id, agent_id, operation, action_id="",
               trace_id="", detail="") -> BusinessAuditRecord:
        record = BusinessAuditRecord(
            audit_id=f"{tenant_id}:{operation}:{len(self.records)}",
            tenant_id=tenant_id, agent_id=agent_id, operation=operation,
            action_id=action_id, trace_id=trace_id, detail=detail,
        )
        self.records.append(record)
        return record

    def list(self):
        return list(self.records)


__all__ = [
    "BusinessAuditRecord",
    "BusinessAuditLogger",
    "OP_ACTION_CREATED",
    "OP_APPROVAL_REQUESTED",
    "OP_APPROVED",
    "OP_EXECUTED",
    "OP_FAILED",
    "OP_ROLLBACK",
    "OPERATIONS",
]
