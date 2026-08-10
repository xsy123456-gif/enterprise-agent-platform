"""Contracts crossing the Supervisor-to-Agent Runtime boundary."""

from dataclasses import dataclass, field
from datetime import datetime
import uuid
from typing import Any

from app.runtime.multi_agent.context import AgentContextEnvelope
from app.runtime.multi_agent.models import (
    AgentError,
    AgentMessageStatus,
    AgentMessageType,
    AgentProvenance,
    AgentResultStatus,
    EvidenceReference,
    utc_now,
)
from app.runtime.multi_agent.validation import validate_transfer_value


@dataclass(frozen=True)
class AgentMessage:
    """Transport-neutral semantic envelope routed by the Supervisor."""

    execution_id: str
    agent_execution_id: str
    invocation_id: str
    sender_agent_id: str
    receiver_agent_id: str
    message_type: AgentMessageType
    payload: dict[str, Any]
    trace_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    parent_span_id: str | None = None
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: AgentMessageStatus = AgentMessageStatus.CREATED
    created_at: datetime = field(default_factory=utc_now)
    schema_version: str = "agent-message.v1"

    def __post_init__(self):
        for name in (
            "message_id", "execution_id", "agent_execution_id", "invocation_id",
            "sender_agent_id", "receiver_agent_id", "trace_id",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        object.__setattr__(self, "message_type", AgentMessageType(self.message_type))
        object.__setattr__(self, "status", AgentMessageStatus(self.status))
        if self.schema_version != "agent-message.v1":
            raise ValueError(f"Unsupported message schema: {self.schema_version}")
        if not isinstance(self.payload, dict) or not isinstance(self.metadata, dict):
            raise TypeError("AgentMessage payload and metadata must be dicts")
        if not isinstance(self.created_at, datetime):
            raise TypeError("AgentMessage created_at must be datetime")
        validate_transfer_value(self.payload, "AgentMessage.payload")
        validate_transfer_value(self.metadata, "AgentMessage.metadata")

    def to_dict(self):
        return {
            "message_id": self.message_id,
            "execution_id": self.execution_id,
            "agent_execution_id": self.agent_execution_id,
            "invocation_id": self.invocation_id,
            "sender_agent_id": self.sender_agent_id,
            "receiver_agent_id": self.receiver_agent_id,
            "message_type": self.message_type.value,
            "payload": validate_transfer_value(self.payload, "payload"),
            "metadata": validate_transfer_value(self.metadata, "metadata"),
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


@dataclass(frozen=True)
class AgentInvocationRequest:
    """A value-only invocation; receiving Runtime rebuilds private context."""

    execution_id: str
    parent_agent: str
    target_agent: str
    capability: str
    input: dict[str, Any]
    trace_id: str
    target_artifact_id: str
    target_artifact_hash: str
    context_envelope: AgentContextEnvelope | None = None
    context_reference: str | None = None
    parent_span_id: str | None = None
    invocation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: str = "agent-invocation.v1"

    def __post_init__(self):
        for name in (
            "invocation_id", "agent_execution_id", "execution_id",
            "parent_agent", "target_agent", "capability", "trace_id",
            "target_artifact_id", "target_artifact_hash",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        if self.schema_version != "agent-invocation.v1":
            raise ValueError(f"Unsupported invocation schema: {self.schema_version}")
        if not isinstance(self.input, dict):
            raise TypeError("input must be a dict")
        if self.context_envelope is not None and not isinstance(
            self.context_envelope, AgentContextEnvelope
        ):
            raise TypeError("context_envelope must be AgentContextEnvelope")
        if self.context_reference is not None and not isinstance(
            self.context_reference, str
        ):
            raise TypeError("context_reference must be a string reference")
        validate_transfer_value(self.input, "AgentInvocationRequest.input")

    @property
    def parent_agent_id(self):
        return self.parent_agent

    @property
    def target_agent_id(self):
        return self.target_agent

    @property
    def input_payload(self):
        return self.input

    def to_dict(self):
        return {
            "invocation_id": self.invocation_id,
            "agent_execution_id": self.agent_execution_id,
            "execution_id": self.execution_id,
            "parent_agent": self.parent_agent,
            "target_agent": self.target_agent,
            "capability": self.capability,
            "input": validate_transfer_value(self.input, "input"),
            "trace_id": self.trace_id,
            "target_artifact_id": self.target_artifact_id,
            "target_artifact_hash": self.target_artifact_hash,
            "context_envelope": (
                self.context_envelope.to_dict() if self.context_envelope else None
            ),
            "context_reference": self.context_reference,
            "parent_span_id": self.parent_span_id,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        if data.get("context_envelope") is not None:
            data["context_envelope"] = AgentContextEnvelope.from_dict(
                data["context_envelope"]
            )
        return cls(**data)


@dataclass(frozen=True)
class AgentExecutionResult:
    """Normalized public result; no Runtime or backend state is exposed."""

    execution_id: str
    agent_execution_id: str
    agent_id: str
    agent_version: str
    artifact_id: str
    artifact_hash: str
    status: AgentResultStatus
    output: Any
    findings: tuple[dict[str, Any], ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()
    errors: tuple[AgentError, ...] = ()
    artifacts: tuple[dict[str, Any], ...] = ()
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: AgentProvenance | None = None
    schema_version: str = "agent-result.v1"

    def __post_init__(self):
        for name in (
            "execution_id", "agent_execution_id", "agent_id", "agent_version",
            "artifact_id", "artifact_hash",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        object.__setattr__(self, "status", AgentResultStatus(self.status))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        if self.schema_version != "agent-result.v1":
            raise ValueError(f"Unsupported result schema: {self.schema_version}")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be a dict")
        validate_transfer_value(self.output, "AgentExecutionResult.output")
        validate_transfer_value(self.findings, "AgentExecutionResult.findings")
        validate_transfer_value(self.artifacts, "AgentExecutionResult.artifacts")
        validate_transfer_value(self.metadata, "AgentExecutionResult.metadata")

    def to_dict(self):
        return {
            "execution_id": self.execution_id,
            "agent_execution_id": self.agent_execution_id,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "artifact_id": self.artifact_id,
            "artifact_hash": self.artifact_hash,
            "status": self.status.value,
            "output": validate_transfer_value(self.output, "output"),
            "findings": validate_transfer_value(self.findings, "findings"),
            "evidence": [item.to_dict() for item in self.evidence],
            "errors": [item.to_dict() for item in self.errors],
            "artifacts": validate_transfer_value(self.artifacts, "artifacts"),
            "confidence": self.confidence,
            "metadata": validate_transfer_value(self.metadata, "metadata"),
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        data["evidence"] = tuple(
            EvidenceReference.from_dict(item) for item in data.get("evidence", [])
        )
        data["errors"] = tuple(
            AgentError.from_dict(item) for item in data.get("errors", [])
        )
        if data.get("provenance") is not None:
            data["provenance"] = AgentProvenance.from_dict(data["provenance"])
        return cls(**data)
