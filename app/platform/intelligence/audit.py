"""Intelligence optimization audit (Phase 17.7)."""

from dataclasses import dataclass, field

from app.core.time import utc_now

OP_OPTIMIZATION_CREATED = "OptimizationCreated"
OP_OPTIMIZATION_APPROVED = "OptimizationApproved"
OP_EXPERIMENT_STARTED = "ExperimentStarted"
OP_VERSION_RELEASED = "VersionReleased"
OP_ROLLBACK_EXECUTED = "RollbackExecuted"
OPERATIONS = frozenset({
    OP_OPTIMIZATION_CREATED, OP_OPTIMIZATION_APPROVED, OP_EXPERIMENT_STARTED,
    OP_VERSION_RELEASED, OP_ROLLBACK_EXECUTED,
})


@dataclass(frozen=True)
class IntelligenceAuditRecord:
    audit_id: str
    agent_id: str
    operation: str
    proposal_id: str = ""
    timestamp: str = field(default_factory=utc_now)
    trace_id: str = ""
    detail: str = ""

    def __post_init__(self):
        if self.operation not in OPERATIONS:
            raise ValueError(f"unknown operation: {self.operation}")

    def to_dict(self) -> dict:
        return {
            "audit_id": self.audit_id,
            "agent_id": self.agent_id,
            "operation": self.operation,
            "proposal_id": self.proposal_id,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "detail": self.detail,
        }


class IntelligenceAuditLogger:

    def __init__(self):
        self.records = []

    def record(self, agent_id, operation, proposal_id="", trace_id="",
               detail="") -> IntelligenceAuditRecord:
        record = IntelligenceAuditRecord(
            audit_id=f"{agent_id}:{operation}:{len(self.records)}",
            agent_id=agent_id, operation=operation, proposal_id=proposal_id,
            trace_id=trace_id, detail=detail,
        )
        self.records.append(record)
        return record

    def list(self):
        return list(self.records)


__all__ = [
    "IntelligenceAuditRecord",
    "IntelligenceAuditLogger",
    "OP_OPTIMIZATION_CREATED",
    "OP_OPTIMIZATION_APPROVED",
    "OP_EXPERIMENT_STARTED",
    "OP_VERSION_RELEASED",
    "OP_ROLLBACK_EXECUTED",
    "OPERATIONS",
]
