from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Any


def utc_now():
    return datetime.now(timezone.utc)


def _datetime(value):
    return datetime.fromisoformat(value) if isinstance(value, str) else value


@dataclass(frozen=True)
class ExecutionTrace:
    trace_id: str
    execution_id: str
    agent_id: str
    artifact_id: str
    backend_type: str
    status: str
    root_span_id: str
    start_time: datetime = field(default_factory=utc_now)
    end_time: datetime | None = None
    agent_version: str = "unknown"
    artifact_hash: str = "unknown"

    def __post_init__(self):
        for name in (
            "trace_id", "execution_id", "agent_id", "artifact_id",
            "backend_type", "status", "root_span_id",
        ):
            if not getattr(self, name):
                raise ValueError(f"{name} is required")

    def to_dict(self):
        return {
            "trace_id": self.trace_id,
            "execution_id": self.execution_id,
            "agent_id": self.agent_id,
            "artifact_id": self.artifact_id,
            "backend_type": self.backend_type,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "root_span_id": self.root_span_id,
            "agent_version": self.agent_version,
            "artifact_hash": self.artifact_hash,
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        data["start_time"] = _datetime(data["start_time"])
        data["end_time"] = _datetime(data.get("end_time"))
        return cls(**data)


@dataclass(frozen=True)
class NodeSpan:
    trace_id: str
    node_id: str
    node_type: str
    status: str
    input_summary: str
    output_summary: str
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_span_id: str | None = None
    start_time: datetime = field(default_factory=utc_now)
    end_time: datetime | None = None
    error: str | None = None
    execution_id: str | None = None
    operation_id: str | None = None
    span_type: str = "NODE"
    name: str | None = None
    agent_id: str | None = None
    agent_version: str | None = None
    artifact_hash: str | None = None
    backend_type: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        for name in ("span_id", "trace_id", "node_id", "node_type", "status"):
            if not getattr(self, name):
                raise ValueError(f"{name} is required")
        if not isinstance(self.input_summary, str) or not isinstance(
            self.output_summary, str
        ):
            raise TypeError("NodeSpan input/output must be summaries, not raw objects")
        if not isinstance(self.attributes, dict):
            raise TypeError("Span attributes must be metadata dict")

    @property
    def duration_ms(self):
        if self.end_time is None:
            return None
        return max(0.0, (self.end_time - self.start_time).total_seconds() * 1000)

    def to_dict(self):
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "node_id": self.node_id,
            "node_type": self.node_type,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "error": self.error,
            "execution_id": self.execution_id,
            "operation_id": self.operation_id,
            "span_type": self.span_type,
            "name": self.name,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "artifact_hash": self.artifact_hash,
            "backend_type": self.backend_type,
            "attributes": dict(self.attributes),
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        data["start_time"] = _datetime(data["start_time"])
        data["end_time"] = _datetime(data.get("end_time"))
        data.pop("duration_ms", None)
        return cls(**data)


@dataclass(frozen=True)
class BackendSpan:
    backend_type: str
    backend_metadata: dict[str, Any]
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str | None = None
    execution_id: str | None = None
    parent_span_id: str | None = None
    operation_id: str | None = None
    status: str = "RUNNING"
    start_time: datetime = field(default_factory=utc_now)
    end_time: datetime | None = None

    def __post_init__(self):
        if not self.span_id or not self.backend_type:
            raise ValueError("BackendSpan span_id and backend_type are required")
        if not isinstance(self.backend_metadata, dict):
            raise TypeError("backend_metadata must be an opaque dict")

    def to_dict(self):
        return {
            "span_id": self.span_id,
            "backend_type": self.backend_type,
            "backend_metadata": dict(self.backend_metadata),
            "trace_id": self.trace_id,
            "execution_id": self.execution_id,
            "parent_span_id": self.parent_span_id,
            "operation_id": self.operation_id,
            "status": self.status,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        data["start_time"] = _datetime(data["start_time"])
        data["end_time"] = _datetime(data.get("end_time"))
        return cls(**data)
