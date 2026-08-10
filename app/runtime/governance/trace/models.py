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

    def __post_init__(self):
        for name in ("span_id", "trace_id", "node_id", "node_type", "status"):
            if not getattr(self, name):
                raise ValueError(f"{name} is required")
        if not isinstance(self.input_summary, str) or not isinstance(
            self.output_summary, str
        ):
            raise TypeError("NodeSpan input/output must be summaries, not raw objects")

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
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        data["start_time"] = _datetime(data["start_time"])
        data["end_time"] = _datetime(data.get("end_time"))
        return cls(**data)


@dataclass(frozen=True)
class BackendSpan:
    backend_type: str
    backend_metadata: dict[str, Any]
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))

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
        }

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))
