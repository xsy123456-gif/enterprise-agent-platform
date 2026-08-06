from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from app.memory.types import CUSTOMER


@dataclass
class MemoryCandidate:
    memory_type: str
    key: str
    content: Any
    source: str


class MemoryPolicy(ABC):
    @abstractmethod
    def extract(self, result, context) -> list[MemoryCandidate]:
        pass


class CustomerMemoryPolicy(MemoryPolicy):
    """Allows only structured CRM customer records into long-term memory."""

    def extract(self, result, context):
        if not isinstance(result, dict):
            return []
        if not all(field in result for field in ("name", "industry", "history")):
            return []
        return [
            MemoryCandidate(
                memory_type=CUSTOMER,
                key=result["name"],
                content={
                    "industry": result["industry"],
                    "history": result["history"],
                },
                source="crm_query",
            )
        ]


class MemoryGuard:
    def __init__(self, memory_service=None, policies: Optional[dict] = None):
        self.memory_service = memory_service
        self.policies = policies or {"customer_memory": CustomerMemoryPolicy()}

    def update(self, result, context, policy_id=None):
        if self.memory_service is None or not policy_id:
            return []
        policy = self.policies.get(policy_id)
        if policy is None:
            return []
        candidates = policy.extract(result, context)
        for candidate in candidates:
            self.memory_service.save(
                candidate.memory_type,
                candidate.key,
                candidate.content,
            )
        return candidates
