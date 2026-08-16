"""Production audit (Phase 15.7).

Records production operations with tenant + agent + trace.  Forbidden:
secret / credential / raw private data are structurally absent.
"""

from dataclasses import dataclass, field

from app.commerce.domain.base import utc_now

OP_AGENT_EXECUTED = "AgentExecuted"
OP_BUDGET_BLOCKED = "BudgetBlocked"
OP_QUOTA_EXCEEDED = "QuotaExceeded"
OP_CIRCUIT_OPENED = "CircuitOpened"
OP_TENANT_ACCESS_DENIED = "TenantAccessDenied"
OPERATIONS = frozenset({
    OP_AGENT_EXECUTED, OP_BUDGET_BLOCKED, OP_QUOTA_EXCEEDED,
    OP_CIRCUIT_OPENED, OP_TENANT_ACCESS_DENIED,
})


@dataclass(frozen=True)
class ProductionAuditRecord:
    audit_id: str
    tenant_id: str
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
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "operation": self.operation,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
        }


class ProductionAuditLogger:

    def __init__(self):
        self.records = []

    def record(self, tenant_id, agent_id, operation, trace_id="") -> ProductionAuditRecord:
        record = ProductionAuditRecord(
            audit_id=f"{tenant_id}:{operation}:{len(self.records)}",
            tenant_id=tenant_id, agent_id=agent_id, operation=operation,
            trace_id=trace_id,
        )
        self.records.append(record)
        return record

    def list(self):
        return list(self.records)


__all__ = [
    "ProductionAuditRecord",
    "ProductionAuditLogger",
    "OP_AGENT_EXECUTED",
    "OP_BUDGET_BLOCKED",
    "OP_QUOTA_EXCEEDED",
    "OP_CIRCUIT_OPENED",
    "OP_TENANT_ACCESS_DENIED",
    "OPERATIONS",
]
