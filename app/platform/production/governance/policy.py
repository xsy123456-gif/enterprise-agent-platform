"""Agent budget policy (Phase 15.4)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentBudgetPolicy:
    agent_id: str
    daily_limit: float = 0.0
    monthly_limit: float = 0.0
    hard_stop: bool = True

    def __post_init__(self):
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if self.daily_limit < 0 or self.monthly_limit < 0:
            raise ValueError("limits must be >= 0")

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "daily_limit": self.daily_limit,
            "monthly_limit": self.monthly_limit,
            "hard_stop": self.hard_stop,
        }


__all__ = ["AgentBudgetPolicy"]
