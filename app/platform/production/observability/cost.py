"""Agent cost tracking (Phase 15.1 observability + 15.4 governance).

Observability records the cost of every execution; budget governance (15.4)
enforces limits on top of these records.
"""

from dataclasses import dataclass, field

from app.commerce.domain.base import utc_now


@dataclass(frozen=True)
class AgentCostRecord:
    execution_id: str
    tenant_id: str
    agent_id: str
    llm_cost: float = 0.0
    tool_cost: float = 0.0
    total_cost: float = 0.0
    at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.execution_id:
            raise ValueError("execution_id is required")

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "llm_cost": self.llm_cost,
            "tool_cost": self.tool_cost,
            "total_cost": self.total_cost,
            "at": self.at,
        }


class CostCollector:

    def __init__(self):
        self._records = []

    def record(self, record: AgentCostRecord):
        self._records.append(record)
        return record

    def total_for(self, agent_id, tenant_id=None):
        total = 0.0
        for record in self._records:
            if record.agent_id != agent_id:
                continue
            if tenant_id is not None and record.tenant_id != tenant_id:
                continue
            total += record.total_cost
        return total

    def list(self):
        return list(self._records)


__all__ = ["AgentCostRecord", "CostCollector"]
