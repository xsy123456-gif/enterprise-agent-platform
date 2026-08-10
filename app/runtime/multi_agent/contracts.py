"""Contracts crossing the Supervisor-to-Agent Runtime boundary."""

from dataclasses import dataclass, field
import json
import uuid
from typing import Any

from app.runtime.contracts import AgentRuntimeState
from app.runtime.multi_agent.models import AgentExecutionStatus


def _copy_json(value, field_name):
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be JSON serializable") from error


def _reject_runtime_state(value, field_name):
    if isinstance(value, AgentRuntimeState):
        raise TypeError(
            f"{field_name} cannot contain another Agent's Runtime State"
        )
    if isinstance(value, dict):
        for item in value.values():
            _reject_runtime_state(item, field_name)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_runtime_state(item, field_name)


@dataclass(frozen=True)
class AgentInvocationRequest:
    """A value-only invocation; Runtime Context never crosses Agent boundaries."""

    execution_id: str
    parent_agent: str
    target_agent: str
    capability: str
    input: dict[str, Any]
    context_reference: str | None = None
    agent_execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        for name in (
            "agent_execution_id", "execution_id", "parent_agent",
            "target_agent", "capability",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        if not isinstance(self.input, dict):
            raise TypeError("input must be a dict")
        if self.context_reference is not None and not isinstance(
            self.context_reference, str
        ):
            raise TypeError("context_reference must be a string reference")
        _reject_runtime_state(self.input, "input")
        _copy_json(self.input, "input")

    def to_dict(self):
        return {
            "agent_execution_id": self.agent_execution_id,
            "execution_id": self.execution_id,
            "parent_agent": self.parent_agent,
            "target_agent": self.target_agent,
            "capability": self.capability,
            "input": _copy_json(self.input, "input"),
            "context_reference": self.context_reference,
        }

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))


@dataclass(frozen=True)
class AgentExecutionResult:
    """The only value returned from an Agent Runtime to its Supervisor."""

    execution_id: str
    agent_id: str
    status: AgentExecutionStatus
    output: Any
    artifacts: tuple[dict[str, Any], ...] = ()
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    agent_execution_id: str | None = None

    def __post_init__(self):
        for name in ("execution_id", "agent_id"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        object.__setattr__(self, "status", AgentExecutionStatus(self.status))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        if self.agent_execution_id is not None and not self.agent_execution_id:
            raise ValueError("agent_execution_id cannot be empty")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be a dict")
        _reject_runtime_state(self.output, "output")
        _copy_json(self.output, "output")
        _copy_json(self.artifacts, "artifacts")
        _copy_json(self.metadata, "metadata")

    def to_dict(self):
        return {
            "agent_execution_id": self.agent_execution_id,
            "execution_id": self.execution_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "output": _copy_json(self.output, "output"),
            "artifacts": _copy_json(self.artifacts, "artifacts"),
            "confidence": self.confidence,
            "metadata": _copy_json(self.metadata, "metadata"),
        }

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))
