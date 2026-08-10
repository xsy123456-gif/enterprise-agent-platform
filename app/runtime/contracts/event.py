from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.runtime.contracts.state import serialize_value


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class RuntimeEventType:
    NODE_STARTED = "node.started"
    NODE_COMPLETED = "node.completed"
    WORKER_STARTED = "worker.started"
    WORKER_COMPLETED = "worker.completed"
    GRAPH_COMPLETED = "graph.completed"
    GRAPH_FAILED = "graph.failed"
    GRAPH_STARTED = "graph.started"
    NODE_FAILED = "node.failed"

    ALL = {
        NODE_STARTED, NODE_COMPLETED, WORKER_STARTED, WORKER_COMPLETED,
        GRAPH_STARTED, GRAPH_COMPLETED, GRAPH_FAILED, NODE_FAILED,
    }


@dataclass(frozen=True)
class RuntimeEvent:
    event_type: str
    task_id: str
    node_id: str | None = None
    timestamp: str = field(default_factory=utc_now)
    payload: dict[str, Any] = field(default_factory=dict)
    operation_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None

    def __post_init__(self):
        if self.event_type not in RuntimeEventType.ALL:
            raise ValueError(f"Unsupported Runtime event type: {self.event_type}")
        if not self.task_id:
            raise ValueError("RuntimeEvent task_id is required")

    def to_dict(self):
        return serialize_value({
            "event_type": self.event_type,
            "task_id": self.task_id,
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "operation_id": self.operation_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
        })

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))
