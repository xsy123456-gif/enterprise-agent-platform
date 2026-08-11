from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def utc_now():
    return datetime.now(timezone.utc)


class ExecutionStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_TOOL = "waiting_tool"
    WAITING_GOVERNANCE = "waiting_governance"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RESUMING = "resuming"


@dataclass(frozen=True)
class ExecutionRecord:
    execution_id: str
    trace_id: str
    agent_id: str
    agent_version: str
    artifact_id: str
    artifact_hash: str
    backend_type: str
    user_id: str | None
    tenant_id: str
    status: ExecutionStatus = ExecutionStatus.CREATED
    current_node: str | None = None
    authorization_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def transition(self, status, current_node=None, authorization_id=None):
        target = ExecutionStatus(status)
        allowed = {
            ExecutionStatus.CREATED: {ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED},
            ExecutionStatus.RUNNING: {
                ExecutionStatus.WAITING_APPROVAL, ExecutionStatus.WAITING_TOOL,
                ExecutionStatus.WAITING_GOVERNANCE,
                ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED,
            },
            ExecutionStatus.WAITING_APPROVAL: {ExecutionStatus.RESUMING, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED},
            ExecutionStatus.WAITING_TOOL: {ExecutionStatus.RUNNING, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED},
            ExecutionStatus.WAITING_GOVERNANCE: {
                ExecutionStatus.RUNNING, ExecutionStatus.RESUMING,
                ExecutionStatus.FAILED,
                ExecutionStatus.CANCELLED,
            },
            ExecutionStatus.RESUMING: {ExecutionStatus.RUNNING, ExecutionStatus.COMPLETED, ExecutionStatus.FAILED},
            ExecutionStatus.COMPLETED: set(),
            ExecutionStatus.FAILED: {ExecutionStatus.RESUMING},
            ExecutionStatus.CANCELLED: set(),
        }
        if target not in allowed[self.status]:
            raise ValueError(f"Invalid execution transition: {self.status.value} -> {target.value}")
        return ExecutionRecord(
            **{**self.__dict__, "status": target,
               "current_node": current_node if current_node is not None else self.current_node,
               "authorization_id": (
                   authorization_id if authorization_id is not None
                   else self.authorization_id
               ),
               "updated_at": utc_now()}
        )

    def to_dict(self):
        return {
            **self.__dict__,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        for field_name in ("created_at", "updated_at"):
            value = data.get(field_name)
            if isinstance(value, str):
                data[field_name] = datetime.fromisoformat(value)
        data["status"] = ExecutionStatus(data["status"])
        return cls(**data)
