"""Human escalation port; the existing Governance flow provides implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from app.runtime.recovery.models import AgentFailure, utc_now


@dataclass(frozen=True)
class FailureEscalationEvent:
    execution_id: str
    agent_execution_id: str
    agent_id: str
    failure_id: str
    reason: str
    details_ref: str | None = None
    escalation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        for name in (
            "escalation_id", "execution_id", "agent_execution_id", "agent_id",
            "failure_id", "reason",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")

    @classmethod
    def from_failure(cls, failure, reason):
        if not isinstance(failure, AgentFailure):
            raise TypeError("failure must be AgentFailure")
        return cls(
            execution_id=failure.execution_id,
            agent_execution_id=failure.agent_execution_id,
            agent_id=failure.agent_id,
            failure_id=failure.failure_id,
            reason=reason,
            details_ref=failure.details_ref,
        )

    def to_dict(self):
        return {
            **self.__dict__,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


class FailureEscalationBoundary(ABC):
    """Port to Governance Approval; it does not implement approval itself."""

    @abstractmethod
    def request(self, event: FailureEscalationEvent):
        pass


class NullFailureEscalationBoundary(FailureEscalationBoundary):
    def request(self, event):
        return event
