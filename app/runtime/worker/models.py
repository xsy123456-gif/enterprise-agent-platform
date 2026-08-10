from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.runtime.contracts.state import AgentRuntimeState, serialize_value


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class WorkerStatus:
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    ALL = {CREATED, RUNNING, COMPLETED, FAILED}
    TRANSITIONS = {
        CREATED: {RUNNING},
        RUNNING: {COMPLETED, FAILED},
        COMPLETED: set(),
        FAILED: set(),
    }


@dataclass(frozen=True)
class WorkerDefinition:
    """Static binding between a Worker role and an Agent subgraph artifact."""

    worker_id: str
    subgraph_ref: str
    execution_policy: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.worker_id or not self.subgraph_ref:
            raise ValueError("WorkerDefinition worker_id and subgraph_ref are required")

    def to_dict(self):
        return {
            "worker_id": self.worker_id,
            "subgraph_ref": self.subgraph_ref,
            "execution_policy": serialize_value(self.execution_policy),
        }

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))


@dataclass
class WorkerInstance:
    """One runtime execution of a statically defined Worker."""

    worker_id: str
    task_id: str
    state: AgentRuntimeState
    status: str = WorkerStatus.CREATED
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.worker_id or not self.task_id:
            raise ValueError("WorkerInstance worker_id and task_id are required")
        if self.task_id != self.state.task_id:
            raise ValueError("WorkerInstance task_id must match Runtime state")
        if self.status not in WorkerStatus.ALL:
            raise ValueError(f"Unsupported Worker status: {self.status}")

    def transition(self, target):
        if target not in WorkerStatus.ALL:
            raise ValueError(f"Unsupported Worker status: {target}")
        if target not in WorkerStatus.TRANSITIONS[self.status]:
            raise ValueError(f"Invalid Worker transition: {self.status} -> {target}")
        self.status = target
        return self

    def start(self):
        return self.transition(WorkerStatus.RUNNING)

    def complete(self):
        return self.transition(WorkerStatus.COMPLETED)

    def fail(self):
        return self.transition(WorkerStatus.FAILED)

    def to_dict(self):
        return {
            "worker_id": self.worker_id,
            "task_id": self.task_id,
            "status": self.status,
            "created_at": self.created_at,
            "state": self.state.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        data["state"] = AgentRuntimeState.from_dict(data["state"])
        return cls(**data)
