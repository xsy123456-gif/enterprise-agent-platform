"""Backend-neutral models for a Supervisor-managed Agent execution graph."""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import json
import uuid
from typing import Any


def utc_now():
    return datetime.now(timezone.utc)


def _json_copy(value, field_name):
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be JSON serializable") from error


class AgentExecutionStatus(str, Enum):
    """Lifecycle shared by an Agent node and its execution record."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class AgentExecutionGraphStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentResultStatus(str, Enum):
    """Public result semantics, independent from ExecutionManager lifecycle."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    DENIED = "denied"
    CANCELLED = "cancelled"


class AgentMessageType(str, Enum):
    INPUT = "INPUT"
    RESULT = "RESULT"
    CONTEXT = "CONTEXT"
    CONTROL = "CONTROL"
    ERROR = "ERROR"


class AgentMessageStatus(str, Enum):
    CREATED = "created"
    VALIDATED = "validated"
    DELIVERED = "delivered"
    REJECTED = "rejected"


@dataclass(frozen=True)
class EvidenceReference:
    type: str
    ref: str
    source: str | None = None

    def __post_init__(self):
        if not self.type or not self.ref:
            raise ValueError("EvidenceReference type and ref are required")

    def to_dict(self):
        return {"type": self.type, "ref": self.ref, "source": self.source}

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))


@dataclass(frozen=True)
class AgentProvenance:
    source_agent_id: str
    source_agent_version: str
    source_artifact_id: str
    source_artifact_hash: str
    source_agent_execution_id: str
    source_message_id: str | None = None

    def __post_init__(self):
        for name in (
            "source_agent_id", "source_agent_version", "source_artifact_id",
            "source_artifact_hash", "source_agent_execution_id",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")

    def to_dict(self):
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))


@dataclass(frozen=True)
class AgentError:
    code: str
    category: str
    message: str
    retryable: bool = False
    details_ref: str | None = None

    def __post_init__(self):
        if not self.code or not self.category or not self.message:
            raise ValueError("AgentError code, category and message are required")
        if not isinstance(self.retryable, bool):
            raise TypeError("AgentError retryable must be bool")

    def to_dict(self):
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))


@dataclass(frozen=True)
class ContextCorrelation:
    execution_id: str
    trace_id: str
    parent_agent_execution_id: str
    invocation_id: str
    source_message_id: str | None = None

    def __post_init__(self):
        for name in (
            "execution_id", "trace_id", "parent_agent_execution_id",
            "invocation_id",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")

    def to_dict(self):
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))


@dataclass(frozen=True)
class AgentNode:
    """One independently versioned Runtime Artifact in a Supervisor graph."""

    agent_id: str
    artifact_id: str
    artifact_hash: str
    capability: str
    input_contract: dict[str, Any] = field(default_factory=dict)
    output_contract: dict[str, Any] = field(default_factory=dict)
    execution_policy: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        for name in ("agent_id", "artifact_id", "artifact_hash", "capability"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        for name in ("input_contract", "output_contract", "execution_policy"):
            value = getattr(self, name)
            if not isinstance(value, dict):
                raise TypeError(f"{name} must be a dict")
            _json_copy(value, name)

    @property
    def node_id(self):
        return self.agent_id

    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "artifact_id": self.artifact_id,
            "artifact_hash": self.artifact_hash,
            "capability": self.capability,
            "input_contract": _json_copy(self.input_contract, "input_contract"),
            "output_contract": _json_copy(self.output_contract, "output_contract"),
            "execution_policy": _json_copy(
                self.execution_policy, "execution_policy"
            ),
        }

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))


@dataclass(frozen=True)
class AgentGraphEdge:
    """Dependency between Supervisor-owned Agent nodes."""

    source: str
    target: str
    condition: str | None = None

    def __post_init__(self):
        if not self.source or not self.target:
            raise ValueError("AgentGraphEdge source and target are required")
        if self.source == self.target:
            raise ValueError("AgentGraphEdge cannot reference itself")

    def to_dict(self):
        return {
            "source": self.source,
            "target": self.target,
            "condition": self.condition,
        }

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))


@dataclass(frozen=True)
class AgentExecutionRecord:
    """Identity and lifecycle evidence for one Agent invocation."""

    execution_id: str
    agent_id: str
    artifact_id: str
    artifact_hash: str
    capability: str
    parent_agent_id: str
    agent_execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: AgentExecutionStatus = AgentExecutionStatus.CREATED
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        for name in (
            "agent_execution_id", "execution_id", "agent_id", "artifact_id",
            "artifact_hash", "capability", "parent_agent_id",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        object.__setattr__(self, "status", AgentExecutionStatus(self.status))
        if not isinstance(self.created_at, datetime) or not isinstance(
            self.updated_at, datetime
        ):
            raise TypeError("Agent execution timestamps must be datetime")

    def to_dict(self):
        return {
            "agent_execution_id": self.agent_execution_id,
            "execution_id": self.execution_id,
            "agent_id": self.agent_id,
            "artifact_id": self.artifact_id,
            "artifact_hash": self.artifact_hash,
            "capability": self.capability,
            "parent_agent_id": self.parent_agent_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def transition(self, status):
        target = AgentExecutionStatus(status)
        allowed = {
            AgentExecutionStatus.CREATED: {
                AgentExecutionStatus.RUNNING,
                AgentExecutionStatus.BLOCKED,
                AgentExecutionStatus.CANCELLED,
            },
            AgentExecutionStatus.RUNNING: {
                AgentExecutionStatus.COMPLETED,
                AgentExecutionStatus.FAILED,
                AgentExecutionStatus.BLOCKED,
                AgentExecutionStatus.CANCELLED,
            },
            AgentExecutionStatus.BLOCKED: {
                AgentExecutionStatus.RUNNING,
                AgentExecutionStatus.CANCELLED,
            },
            AgentExecutionStatus.COMPLETED: set(),
            AgentExecutionStatus.FAILED: set(),
            AgentExecutionStatus.CANCELLED: set(),
        }
        if target not in allowed[self.status]:
            raise ValueError(
                "Invalid Agent execution transition: "
                f"{self.status.value} -> {target.value}"
            )
        return replace(self, status=target, updated_at=utc_now())

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        for name in ("created_at", "updated_at"):
            if isinstance(data.get(name), str):
                data[name] = datetime.fromisoformat(data[name])
        return cls(**data)
