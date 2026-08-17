"""Agent improvement lifecycle (Phase 17.3)."""

from dataclasses import dataclass, field

from app.core.time import utc_now
from app.platform.intelligence.errors import ImprovementError

IMPROVEMENT_CREATED = "CREATED"
IMPROVEMENT_VALIDATED = "VALIDATED"
IMPROVEMENT_REVIEWING = "REVIEWING"
IMPROVEMENT_APPROVED = "APPROVED"
IMPROVEMENT_IMPLEMENTING = "IMPLEMENTING"
IMPROVEMENT_TESTING = "TESTING"
IMPROVEMENT_RELEASED = "RELEASED"
IMPROVEMENT_ROLLED_BACK = "ROLLED_BACK"
IMPROVEMENT_STATUSES = frozenset({
    IMPROVEMENT_CREATED, IMPROVEMENT_VALIDATED, IMPROVEMENT_REVIEWING,
    IMPROVEMENT_APPROVED, IMPROVEMENT_IMPLEMENTING, IMPROVEMENT_TESTING,
    IMPROVEMENT_RELEASED, IMPROVEMENT_ROLLED_BACK,
})

_TRANSITIONS = {
    IMPROVEMENT_CREATED: {IMPROVEMENT_VALIDATED},
    IMPROVEMENT_VALIDATED: {IMPROVEMENT_REVIEWING},
    IMPROVEMENT_REVIEWING: {IMPROVEMENT_APPROVED},
    IMPROVEMENT_APPROVED: {IMPROVEMENT_IMPLEMENTING},
    IMPROVEMENT_IMPLEMENTING: {IMPROVEMENT_TESTING},
    IMPROVEMENT_TESTING: {IMPROVEMENT_RELEASED, IMPROVEMENT_ROLLED_BACK},
    IMPROVEMENT_RELEASED: {IMPROVEMENT_ROLLED_BACK},
    IMPROVEMENT_ROLLED_BACK: set(),
}


@dataclass(frozen=True)
class AgentImprovementRequest:
    request_id: str
    proposal_id: str
    target_agent: str
    change_type: str = ""
    approval_status: str = "PENDING"
    created_by: str = ""
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.request_id:
            raise ValueError("request_id is required")
        if not self.proposal_id:
            raise ValueError("proposal_id is required")
        if not self.target_agent:
            raise ValueError("target_agent is required")

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "proposal_id": self.proposal_id,
            "target_agent": self.target_agent,
            "change_type": self.change_type,
            "approval_status": self.approval_status,
            "created_by": self.created_by,
            "created_at": self.created_at,
        }


class ImprovementLifecycle:

    def __init__(self):
        self._status = {}

    def create(self, request: AgentImprovementRequest):
        self._status[request.request_id] = IMPROVEMENT_CREATED
        return request

    def transition(self, request_id, target):
        current = self._status.get(request_id)
        if current is None:
            raise ImprovementError(f"unknown improvement request {request_id!r}")
        if target not in _TRANSITIONS[current]:
            raise ImprovementError(
                f"cannot transition {request_id!r} from {current!r} to {target!r}"
            )
        self._status[request_id] = target
        return target

    def status(self, request_id):
        return self._status.get(request_id)

    def release(self, request_id):
        return self.transition(request_id, IMPROVEMENT_RELEASED)

    def rollback(self, request_id):
        return self.transition(request_id, IMPROVEMENT_ROLLED_BACK)


__all__ = [
    "AgentImprovementRequest",
    "ImprovementLifecycle",
    "IMPROVEMENT_STATUSES",
    "IMPROVEMENT_CREATED",
    "IMPROVEMENT_VALIDATED",
    "IMPROVEMENT_REVIEWING",
    "IMPROVEMENT_APPROVED",
    "IMPROVEMENT_IMPLEMENTING",
    "IMPROVEMENT_TESTING",
    "IMPROVEMENT_RELEASED",
    "IMPROVEMENT_ROLLED_BACK",
]
