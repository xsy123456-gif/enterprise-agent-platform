"""Agent experiment model (Phase 17.4)."""

from dataclasses import dataclass, field

from app.commerce.domain.base import utc_now

STRATEGY_SHADOW = "SHADOW"
STRATEGY_AB_TEST = "AB_TEST"
STRATEGY_CANARY = "CANARY"
STRATEGIES = frozenset({STRATEGY_SHADOW, STRATEGY_AB_TEST, STRATEGY_CANARY})

EXPERIMENT_RUNNING = "RUNNING"
EXPERIMENT_COMPLETED = "COMPLETED"
EXPERIMENT_ROLLED_BACK = "ROLLED_BACK"
EXPERIMENT_STATUSES = frozenset({EXPERIMENT_RUNNING, EXPERIMENT_COMPLETED,
                                 EXPERIMENT_ROLLED_BACK})


@dataclass(frozen=True)
class AgentExperiment:
    experiment_id: str
    control_version: str
    candidate_version: str
    strategy: str = STRATEGY_SHADOW
    traffic_ratio: float = 0.0
    status: str = EXPERIMENT_RUNNING
    metrics: dict = field(default_factory=dict)
    start_time: str = field(default_factory=utc_now)
    end_time: str = ""

    def __post_init__(self):
        object.__setattr__(self, "metrics", dict(self.metrics or {}))
        if not self.experiment_id:
            raise ValueError("experiment_id is required")
        if not self.control_version:
            raise ValueError("control_version is required")
        if not self.candidate_version:
            raise ValueError("candidate_version is required")
        if self.strategy not in STRATEGIES:
            raise ValueError(f"unknown strategy: {self.strategy}")
        if not (0.0 <= self.traffic_ratio <= 1.0):
            raise ValueError("traffic_ratio must be in [0, 1]")

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "control_version": self.control_version,
            "candidate_version": self.candidate_version,
            "strategy": self.strategy,
            "traffic_ratio": self.traffic_ratio,
            "status": self.status,
            "metrics": dict(self.metrics),
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


__all__ = [
    "AgentExperiment",
    "STRATEGIES",
    "STRATEGY_SHADOW",
    "STRATEGY_AB_TEST",
    "STRATEGY_CANARY",
    "EXPERIMENT_STATUSES",
    "EXPERIMENT_RUNNING",
    "EXPERIMENT_COMPLETED",
    "EXPERIMENT_ROLLED_BACK",
]
