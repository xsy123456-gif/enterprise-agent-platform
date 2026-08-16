"""Optimization proposal model (Phase 17.2)."""

from dataclasses import dataclass, field

from app.commerce.domain.base import utc_now

TARGET_AGENT = "AGENT"
TARGET_SKILL = "SKILL"
TARGET_PLAN = "PLAN"
TARGET_PROMPT = "PROMPT"
TARGET_KNOWLEDGE = "KNOWLEDGE"
TARGET_POLICY = "POLICY"
TARGET_TYPES = frozenset({
    TARGET_AGENT, TARGET_SKILL, TARGET_PLAN, TARGET_PROMPT, TARGET_KNOWLEDGE,
    TARGET_POLICY,
})

RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"
RISK_LEVELS = frozenset({RISK_LOW, RISK_MEDIUM, RISK_HIGH})

PROPOSAL_CREATED = "CREATED"
PROPOSAL_APPROVED = "APPROVED"
PROPOSAL_REJECTED = "REJECTED"
PROPOSAL_STATUSES = frozenset({PROPOSAL_CREATED, PROPOSAL_APPROVED,
                               PROPOSAL_REJECTED})


@dataclass(frozen=True)
class OptimizationProposal:
    proposal_id: str
    target_type: str
    target_id: str
    current_version: str = ""
    suggested_change: str = ""
    reason: str = ""
    evidence: dict = field(default_factory=dict)
    risk_level: str = RISK_LOW
    status: str = PROPOSAL_CREATED
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        object.__setattr__(self, "evidence", dict(self.evidence or {}))
        if not self.proposal_id:
            raise ValueError("proposal_id is required")
        if self.target_type not in TARGET_TYPES:
            raise ValueError(f"unknown target type: {self.target_type}")
        if not self.target_id:
            raise ValueError("target_id is required")
        if self.risk_level not in RISK_LEVELS:
            raise ValueError(f"unknown risk level: {self.risk_level}")
        if self.status not in PROPOSAL_STATUSES:
            raise ValueError(f"unknown proposal status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "current_version": self.current_version,
            "suggested_change": self.suggested_change,
            "reason": self.reason,
            "evidence": dict(self.evidence),
            "risk_level": self.risk_level,
            "status": self.status,
            "created_at": self.created_at,
        }


__all__ = [
    "OptimizationProposal",
    "TARGET_TYPES",
    "TARGET_AGENT",
    "TARGET_SKILL",
    "TARGET_PLAN",
    "TARGET_PROMPT",
    "TARGET_KNOWLEDGE",
    "TARGET_POLICY",
    "RISK_LEVELS",
    "RISK_LOW",
    "RISK_MEDIUM",
    "RISK_HIGH",
    "PROPOSAL_STATUSES",
    "PROPOSAL_CREATED",
    "PROPOSAL_APPROVED",
    "PROPOSAL_REJECTED",
]
