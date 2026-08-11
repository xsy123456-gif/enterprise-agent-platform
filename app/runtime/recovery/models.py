"""Backend-neutral failure, attempt and recovery decision contracts."""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any


def utc_now():
    return datetime.now(timezone.utc)


class FailureType(str, Enum):
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    POLICY = "POLICY"
    TIMEOUT = "TIMEOUT"
    DEPENDENCY = "DEPENDENCY"
    VALIDATION = "VALIDATION"
    UNKNOWN = "UNKNOWN"


class AttemptStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    SUCCESS = "SUCCESS"


class RecoveryAction(str, Enum):
    RETRY = "RETRY"
    RESUME = "RESUME"
    SKIP = "SKIP"
    ESCALATE = "ESCALATE"
    STOP = "STOP"


@dataclass(frozen=True)
class AgentFailure:
    execution_id: str
    agent_execution_id: str
    agent_id: str
    attempt_id: str
    failure_type: FailureType
    error_code: str
    retryable: bool
    details_ref: str | None = None
    failure_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        for name in (
            "failure_id", "execution_id", "agent_execution_id", "agent_id",
            "attempt_id", "error_code",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        object.__setattr__(self, "failure_type", FailureType(self.failure_type))
        if not isinstance(self.retryable, bool):
            raise TypeError("retryable must be bool")
        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be datetime")

    def to_dict(self):
        return {
            "failure_id": self.failure_id,
            "execution_id": self.execution_id,
            "agent_execution_id": self.agent_execution_id,
            "agent_id": self.agent_id,
            "attempt_id": self.attempt_id,
            "failure_type": self.failure_type.value,
            "error_code": self.error_code,
            "retryable": self.retryable,
            "details_ref": self.details_ref,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


@dataclass(frozen=True)
class AgentAttemptRecord:
    agent_execution_id: str
    attempt_number: int
    attempt_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: AttemptStatus = AttemptStatus.CREATED
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failure_id: str | None = None

    def __post_init__(self):
        if not self.attempt_id or not self.agent_execution_id:
            raise ValueError("attempt_id and agent_execution_id are required")
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be at least 1")
        object.__setattr__(self, "status", AttemptStatus(self.status))

    def transition(self, status, failure_id=None):
        target = AttemptStatus(status)
        allowed = {
            AttemptStatus.CREATED: {AttemptStatus.RUNNING, AttemptStatus.RETRYING},
            AttemptStatus.RETRYING: {AttemptStatus.RUNNING},
            AttemptStatus.RUNNING: {AttemptStatus.FAILED, AttemptStatus.SUCCESS},
            AttemptStatus.FAILED: set(),
            AttemptStatus.SUCCESS: set(),
        }
        if target not in allowed[self.status]:
            raise ValueError(
                f"Invalid attempt transition: {self.status.value} -> {target.value}"
            )
        now = utc_now()
        return replace(
            self,
            status=target,
            started_at=(now if target is AttemptStatus.RUNNING else self.started_at),
            completed_at=(
                now if target in {AttemptStatus.FAILED, AttemptStatus.SUCCESS}
                else self.completed_at
            ),
            failure_id=failure_id if failure_id is not None else self.failure_id,
        )

    def to_dict(self):
        return {
            "attempt_id": self.attempt_id,
            "agent_execution_id": self.agent_execution_id,
            "attempt_number": self.attempt_number,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "failure_id": self.failure_id,
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        for name in ("started_at", "completed_at"):
            if isinstance(data.get(name), str):
                data[name] = datetime.fromisoformat(data[name])
        return cls(**data)


@dataclass(frozen=True)
class RetryDecision:
    action: RecoveryAction
    retry_number: int
    delay_seconds: float = 0.0
    reason: str = ""

    def __post_init__(self):
        object.__setattr__(self, "action", RecoveryAction(self.action))
        if self.retry_number < 0 or self.delay_seconds < 0:
            raise ValueError("retry_number and delay_seconds cannot be negative")


@dataclass(frozen=True)
class RecoveryOutcome:
    result: Any
    attempts: tuple[AgentAttemptRecord, ...]
    failures: tuple[AgentFailure, ...]
    action: RecoveryAction

    def __post_init__(self):
        object.__setattr__(self, "attempts", tuple(self.attempts))
        object.__setattr__(self, "failures", tuple(self.failures))
        object.__setattr__(self, "action", RecoveryAction(self.action))
