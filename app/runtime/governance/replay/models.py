from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Any


def utc_now():
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ReplayRecord:
    execution_id: str
    artifact_hash: str
    initial_state_ref: str
    event_stream_ref: str
    checkpoint_refs: tuple[str, ...]
    created_at: datetime = field(default_factory=utc_now)
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        for name in (
            "record_id", "execution_id", "artifact_hash", "initial_state_ref",
            "event_stream_ref",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        if not isinstance(self.checkpoint_refs, tuple) or not all(
            isinstance(reference, str) and reference
            for reference in self.checkpoint_refs
        ):
            raise TypeError("checkpoint_refs must be a tuple of non-empty references")
        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be datetime")

    def to_dict(self):
        return {
            "record_id": self.record_id,
            "execution_id": self.execution_id,
            "artifact_hash": self.artifact_hash,
            "initial_state_ref": self.initial_state_ref,
            "event_stream_ref": self.event_stream_ref,
            "checkpoint_refs": list(self.checkpoint_refs),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        data["checkpoint_refs"] = tuple(data["checkpoint_refs"])
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


@dataclass(frozen=True)
class BackendComparison:
    execution_id: str
    backend_a: str
    backend_b: str
    trace_diff: dict[str, Any]
    result_diff: dict[str, Any]

    def __post_init__(self):
        for name in ("execution_id", "backend_a", "backend_b"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        if not isinstance(self.trace_diff, dict):
            raise TypeError("trace_diff must be a dict")
        if not isinstance(self.result_diff, dict):
            raise TypeError("result_diff must be a dict")

    def to_dict(self):
        return {
            "execution_id": self.execution_id,
            "backend_a": self.backend_a,
            "backend_b": self.backend_b,
            "trace_diff": dict(self.trace_diff),
            "result_diff": dict(self.result_diff),
        }

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))
