from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Any


def utc_now():
    return datetime.now(timezone.utc)


class RuntimeEventType:
    GRAPH_STARTED = "graph.started"
    GRAPH_COMPLETED = "graph.completed"
    GRAPH_FAILED = "graph.failed"
    NODE_STARTED = "node.started"
    NODE_COMPLETED = "node.completed"
    NODE_FAILED = "node.failed"
    WORKER_STARTED = "worker.started"
    WORKER_COMPLETED = "worker.completed"
    WORKER_FAILED = "worker.failed"
    TOOL_CALLED = "tool.called"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"
    TOOL_DENIED = "tool.denied"
    MEMORY_RETRIEVED = "memory.retrieved"
    MEMORY_SUBMITTED = "memory.submitted"
    GOVERNANCE_CHECKED = "governance.checked"
    GUARD_CHECKED = "guard.checked"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_COMPLETED = "approval.completed"
    EXECUTION_RESUMED = "execution.resumed"
    RESPONSE_COMPLETED = "response.completed"
    MEMORY_WRITE_REQUESTED = "memory.write.requested"
    MEMORY_WRITE_COMPLETED = "memory.write.completed"
    MEMORY_WRITE_FAILED = "memory.write.failed"
    EXECUTION_CREATED = "execution.created"
    EXECUTION_STARTED = "execution.started"
    EXECUTION_WAITING = "execution.waiting"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    CHECKPOINT_CREATED = "checkpoint.created"
    CHECKPOINT_RESTORED = "checkpoint.restored"
    EXECUTION_RETRY_REQUESTED = "execution.retry_requested"
    EXECUTION_CANCELLED = "execution.cancelled"
    AGENT_MESSAGE_CREATED = "agent.message.created"
    AGENT_MESSAGE_DELIVERED = "agent.message.delivered"
    AGENT_MESSAGE_REJECTED = "agent.message.rejected"

    ALL = {
        GRAPH_STARTED, GRAPH_COMPLETED, GRAPH_FAILED,
        NODE_STARTED, NODE_COMPLETED, NODE_FAILED,
        WORKER_STARTED, WORKER_COMPLETED, WORKER_FAILED,
        TOOL_CALLED, TOOL_COMPLETED, TOOL_FAILED, TOOL_DENIED,
        MEMORY_RETRIEVED, MEMORY_SUBMITTED, GOVERNANCE_CHECKED,
        GUARD_CHECKED, APPROVAL_REQUESTED, APPROVAL_COMPLETED,
        EXECUTION_RESUMED,
        RESPONSE_COMPLETED, MEMORY_WRITE_REQUESTED,
        MEMORY_WRITE_COMPLETED, MEMORY_WRITE_FAILED,
        EXECUTION_CREATED, EXECUTION_STARTED, EXECUTION_WAITING,
        EXECUTION_COMPLETED, EXECUTION_FAILED, CHECKPOINT_CREATED,
        CHECKPOINT_RESTORED, EXECUTION_RETRY_REQUESTED, EXECUTION_CANCELLED,
        AGENT_MESSAGE_CREATED, AGENT_MESSAGE_DELIVERED, AGENT_MESSAGE_REJECTED,
    }


@dataclass(frozen=True)
class RuntimeEvent:
    event_type: str
    execution_id: str
    trace_id: str
    agent_id: str
    agent_version: str
    artifact_id: str
    artifact_hash: str
    backend_type: str
    status: str
    node_id: str | None = None
    worker_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    backend_metadata: dict[str, Any] = field(default_factory=dict)
    operation_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    parent_agent_id: str | None = None
    agent_execution_id: str | None = None
    invocation_id: str | None = None
    message_id: str | None = None
    parent_agent_execution_id: str | None = None
    child_agent_execution_id: str | None = None
    graph_node_id: str | None = None
    parallel_group_id: str | None = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        if self.event_type not in RuntimeEventType.ALL:
            raise ValueError(f"Unsupported Runtime evidence event: {self.event_type}")
        required = (
            "event_id", "execution_id", "trace_id", "agent_id", "agent_version",
            "artifact_id", "artifact_hash", "backend_type", "status",
        )
        for name in required:
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        if not isinstance(self.payload, dict):
            raise TypeError("payload must be a dict")
        if not isinstance(self.backend_metadata, dict):
            raise TypeError("backend_metadata must be an opaque dict")
        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be datetime")

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "artifact_id": self.artifact_id,
            "artifact_hash": self.artifact_hash,
            "backend_type": self.backend_type,
            "node_id": self.node_id,
            "worker_id": self.worker_id,
            "status": self.status,
            "payload": dict(self.payload),
            "backend_metadata": dict(self.backend_metadata),
            "operation_id": self.operation_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "parent_agent_id": self.parent_agent_id,
            "agent_execution_id": self.agent_execution_id,
            "invocation_id": self.invocation_id,
            "message_id": self.message_id,
            "parent_agent_execution_id": self.parent_agent_execution_id,
            "child_agent_execution_id": self.child_agent_execution_id,
            "graph_node_id": self.graph_node_id,
            "parallel_group_id": self.parallel_group_id,
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            data["timestamp"] = datetime.fromisoformat(timestamp)
        return cls(**data)
