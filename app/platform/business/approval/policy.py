"""Approval policy (Phase 16.2)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ApprovalPolicy:
    policy_id: str
    action_type: str
    risk_level: str
    required_approvers: tuple[str, ...] = ()
    timeout: int = 0
    auto_approve: bool = False

    def __post_init__(self):
        object.__setattr__(self, "required_approvers",
                           tuple(self.required_approvers or ()))
        if not self.policy_id:
            raise ValueError("policy_id is required")
        if not self.action_type:
            raise ValueError("action_type is required")

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "action_type": self.action_type,
            "risk_level": self.risk_level,
            "required_approvers": list(self.required_approvers),
            "timeout": self.timeout,
            "auto_approve": self.auto_approve,
        }


__all__ = ["ApprovalPolicy"]
