"""Business action domain (Phase 16.3).

The agent only produces an ``ActionProposal`` (a recommendation); the actual
``BusinessAction`` is owned and executed by the Action Runtime — an agent never
executes a business action itself.
"""

from dataclasses import dataclass, field

from app.platform.business.approval.request import RISK_LOW

ACTION_CREATED = "CREATED"
ACTION_WAITING_APPROVAL = "WAITING_APPROVAL"
ACTION_APPROVED = "APPROVED"
ACTION_EXECUTING = "EXECUTING"
ACTION_SUCCEEDED = "SUCCEEDED"
ACTION_FAILED = "FAILED"
ACTION_CANCELLED = "CANCELLED"
ACTION_STATUSES = frozenset({
    ACTION_CREATED, ACTION_WAITING_APPROVAL, ACTION_APPROVED, ACTION_EXECUTING,
    ACTION_SUCCEEDED, ACTION_FAILED, ACTION_CANCELLED,
})


@dataclass(frozen=True)
class ActionProposal:
    proposal_id: str
    agent_id: str
    recommendation: str = ""
    expected_impact: str = ""
    risk_level: str = RISK_LOW
    action_type: str = ""
    target: str = ""
    parameters: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "parameters", dict(self.parameters or {}))
        if not self.proposal_id:
            raise ValueError("proposal_id is required")
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if not self.action_type:
            raise ValueError("action_type is required")

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "agent_id": self.agent_id,
            "recommendation": self.recommendation,
            "expected_impact": self.expected_impact,
            "risk_level": self.risk_level,
            "action_type": self.action_type,
            "target": self.target,
            "parameters": dict(self.parameters),
        }


@dataclass(frozen=True)
class BusinessAction:
    action_id: str
    action_type: str
    target: str = ""
    parameters: dict = field(default_factory=dict)
    risk_level: str = RISK_LOW
    created_by: str = ""
    status: str = ACTION_CREATED

    def __post_init__(self):
        object.__setattr__(self, "parameters", dict(self.parameters or {}))
        if not self.action_id:
            raise ValueError("action_id is required")
        if not self.action_type:
            raise ValueError("action_type is required")
        if self.status not in ACTION_STATUSES:
            raise ValueError(f"unknown action status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target": self.target,
            "parameters": dict(self.parameters),
            "risk_level": self.risk_level,
            "created_by": self.created_by,
            "status": self.status,
        }


__all__ = [
    "ActionProposal",
    "BusinessAction",
    "ACTION_STATUSES",
    "ACTION_CREATED",
    "ACTION_WAITING_APPROVAL",
    "ACTION_APPROVED",
    "ACTION_EXECUTING",
    "ACTION_SUCCEEDED",
    "ACTION_FAILED",
    "ACTION_CANCELLED",
]
