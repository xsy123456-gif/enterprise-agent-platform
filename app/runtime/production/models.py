from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentLifecycleState(str, Enum):
    CREATED = "created"
    REGISTERED = "registered"
    VALIDATED = "validated"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class AgentLifecycleRecord:
    agent_id: str
    state: AgentLifecycleState = AgentLifecycleState.CREATED
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.agent_id:
            raise ValueError("agent_id is required")
        object.__setattr__(self, "state", AgentLifecycleState(self.state))


@dataclass(frozen=True)
class ArtifactBinding:
    artifact_id: str
    artifact_hash: str
    deployment_version: str

    def __post_init__(self):
        for name in ("artifact_id", "artifact_hash", "deployment_version"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")


class RolloutStrategy(str, Enum):
    IMMEDIATE = "immediate"
    CANARY = "canary"
    PERCENTAGE = "percentage"


@dataclass(frozen=True)
class AgentDeploymentPolicy:
    agent_id: str
    active_artifact: ArtifactBinding
    candidate_artifact: ArtifactBinding | None = None
    rollout_strategy: RolloutStrategy = RolloutStrategy.IMMEDIATE
    rollout_percentage: int = 0
    rollback_policy: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if not isinstance(self.active_artifact, ArtifactBinding):
            raise TypeError("active_artifact must be ArtifactBinding")
        if self.candidate_artifact is not None and not isinstance(
            self.candidate_artifact, ArtifactBinding
        ):
            raise TypeError("candidate_artifact must be ArtifactBinding")
        object.__setattr__(self, "rollout_strategy", RolloutStrategy(self.rollout_strategy))
        if not 0 <= self.rollout_percentage <= 100:
            raise ValueError("rollout_percentage must be between 0 and 100")
        if self.candidate_artifact is None and self.rollout_percentage:
            raise ValueError("rollout_percentage requires candidate_artifact")
        if not isinstance(self.rollback_policy, dict):
            raise TypeError("rollback_policy must be a dict")


@dataclass(frozen=True)
class AgentExecutionQuota:
    agent_id: str
    max_parallel_execution: int
    max_execution_time: float
    max_tool_calls: int
    max_token_usage: int
    policy_version: str = "1"

    def __post_init__(self):
        if not self.agent_id or not self.policy_version:
            raise ValueError("agent_id and policy_version are required")
        if self.max_parallel_execution < 1:
            raise ValueError("max_parallel_execution must be positive")
        if self.max_execution_time <= 0:
            raise ValueError("max_execution_time must be positive")
        if self.max_tool_calls < 0 or self.max_token_usage < 0:
            raise ValueError("tool and token limits cannot be negative")

    def snapshot(self) -> dict[str, Any]:
        return {
            "max_parallel_execution": self.max_parallel_execution,
            "max_execution_time": self.max_execution_time,
            "max_tool_calls": self.max_tool_calls,
            "max_token_usage": self.max_token_usage,
            "policy_version": self.policy_version,
        }


@dataclass(frozen=True)
class QuotaUsage:
    execution_time: float = 0
    tool_calls: int = 0
    token_usage: int = 0


@dataclass(frozen=True)
class QuotaDecision:
    allowed: bool
    reason: str
    quota_snapshot: dict[str, Any]
    active_executions: int
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True)
class ProductionExecutionPermit:
    agent_id: str
    artifact: ArtifactBinding
    quota_decision: QuotaDecision
    runtime_health: "AgentHealthReport"
    runtime_policy_version: str


class AgentHealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class AgentHealthReport:
    agent_id: str
    status: AgentHealthStatus
    checks: dict[str, bool]
    reasons: tuple[str, ...] = ()
    checked_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        object.__setattr__(self, "status", AgentHealthStatus(self.status))
        object.__setattr__(self, "reasons", tuple(self.reasons))


class EventDeliveryStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass(frozen=True)
class EventDeliveryRecord:
    event_id: str
    consumer_id: str
    status: EventDeliveryStatus = EventDeliveryStatus.PENDING
    attempts: int = 0
    last_error: str | None = None
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.event_id or not self.consumer_id:
            raise ValueError("event_id and consumer_id are required")
        object.__setattr__(self, "status", EventDeliveryStatus(self.status))


@dataclass(frozen=True)
class DeadLetterRecord:
    event: Any
    consumer_id: str
    attempts: int
    error: str
    failed_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class AgentPrincipal:
    agent_id: str
    artifact_hash: str
    trust_level: str
    issuer: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        for name in ("agent_id", "artifact_hash", "trust_level", "issuer"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
