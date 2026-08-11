"""Retry and graph recovery policies; these grant no authorization."""

from dataclasses import dataclass, field
from enum import Enum

from app.runtime.recovery.models import FailureType, RecoveryAction


class BackoffStrategy(str, Enum):
    NONE = "NONE"
    FIXED = "FIXED"
    EXPONENTIAL = "EXPONENTIAL"


@dataclass(frozen=True)
class AgentRetryPolicy:
    max_attempts: int = 1
    retryable_failures: frozenset[FailureType] = field(default_factory=lambda: frozenset({
        FailureType.TIMEOUT, FailureType.TRANSIENT,
    }))
    backoff_strategy: BackoffStrategy = BackoffStrategy.NONE
    backoff_seconds: float = 0.0
    fallback_strategy: RecoveryAction = RecoveryAction.STOP

    def __post_init__(self):
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        object.__setattr__(self, "retryable_failures", frozenset(
            FailureType(item) for item in self.retryable_failures
        ))
        object.__setattr__(self, "backoff_strategy", BackoffStrategy(self.backoff_strategy))
        object.__setattr__(self, "fallback_strategy", RecoveryAction(self.fallback_strategy))
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")

    def delay_for(self, retry_number):
        if self.backoff_strategy is BackoffStrategy.NONE:
            return 0.0
        if self.backoff_strategy is BackoffStrategy.FIXED:
            return self.backoff_seconds
        return self.backoff_seconds * (2 ** max(0, retry_number - 1))


@dataclass(frozen=True)
class GraphRecoveryPolicy:
    failure_strategy: dict[str, RecoveryAction] = field(default_factory=dict)
    continue_on_partial_failure: bool = False
    max_graph_retry: int = 0

    def __post_init__(self):
        object.__setattr__(self, "failure_strategy", {
            agent_id: RecoveryAction(action)
            for agent_id, action in self.failure_strategy.items()
        })
        if self.max_graph_retry < 0:
            raise ValueError("max_graph_retry cannot be negative")

    def action_for(self, agent_id, fallback=RecoveryAction.STOP):
        return self.failure_strategy.get(agent_id, RecoveryAction(fallback))
