from dataclasses import dataclass, field
from datetime import datetime
import uuid

from app.runtime.contracts.event import RuntimeEvent as InternalRuntimeEvent
from app.runtime.governance.events import RuntimeEvent as GovernanceRuntimeEvent


@dataclass(frozen=True)
class RuntimeEventContext:
    execution_id: str
    trace_id: str
    agent_id: str
    agent_version: str
    artifact_id: str
    artifact_hash: str
    backend_type: str
    worker_id: str | None = None
    parent_agent_id: str | None = None
    agent_execution_id: str | None = None
    backend_metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        for name in (
            "execution_id", "trace_id", "agent_id", "agent_version",
            "artifact_id", "artifact_hash", "backend_type",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        if not isinstance(self.backend_metadata, dict):
            raise TypeError("backend_metadata must be an opaque dict")


class RuntimeEventMapper:
    """Explicitly maps internal backend events into Governance evidence."""

    EVENT_TYPES = {
        "node.started": "node.started",
        "node.completed": "node.completed",
        "node.failed": "node.failed",
        "worker.started": "worker.started",
        "worker.completed": "worker.completed",
        "worker.failed": "worker.failed",
        "graph.completed": "graph.completed",
        "graph.failed": "graph.failed",
        "graph.started": "graph.started",
    }

    def map(self, event: InternalRuntimeEvent, context: RuntimeEventContext):
        if not isinstance(event, InternalRuntimeEvent):
            raise TypeError("event must be an internal RuntimeEvent")
        governance_type = self.EVENT_TYPES.get(event.event_type)
        if governance_type is None:
            return None
        timestamp = event.timestamp
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        is_node = governance_type.startswith("node.")
        payload = dict(event.payload)
        metadata = dict(context.backend_metadata)
        metadata["legacy_event_type"] = event.event_type
        if event.node_id and not is_node:
            metadata["legacy_node_id"] = event.node_id
        return GovernanceRuntimeEvent(
            event_id=str(uuid.uuid4()),
            event_type=governance_type,
            timestamp=timestamp,
            execution_id=context.execution_id,
            trace_id=context.trace_id,
            agent_id=context.agent_id,
            agent_version=context.agent_version,
            artifact_id=context.artifact_id,
            artifact_hash=context.artifact_hash,
            backend_type=context.backend_type,
            node_id=event.node_id if is_node else None,
            worker_id=context.worker_id,
            status=event.event_type.rsplit(".", 1)[-1],
            payload=payload,
            backend_metadata=metadata,
            operation_id=event.operation_id,
            span_id=event.span_id,
            parent_span_id=event.parent_span_id,
            parent_agent_id=context.parent_agent_id,
            agent_execution_id=context.agent_execution_id,
        )
