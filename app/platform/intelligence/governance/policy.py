"""Optimization policy (Phase 17.6)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OptimizationPolicy:
    policy_id: str
    target_type: str
    risk_level: str
    require_approval: bool = True
    forbidden: bool = False
    max_change_scope: str = ""

    def __post_init__(self):
        if not self.policy_id:
            raise ValueError("policy_id is required")
        if not self.target_type:
            raise ValueError("target_type is required")
        if not self.risk_level:
            raise ValueError("risk_level is required")

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "target_type": self.target_type,
            "risk_level": self.risk_level,
            "require_approval": self.require_approval,
            "forbidden": self.forbidden,
            "max_change_scope": self.max_change_scope,
        }


__all__ = ["OptimizationPolicy"]
