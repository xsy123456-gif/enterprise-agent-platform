from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from app.orchestration.models import StepStatus


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class Task:
    user_query: str
    context: dict[str, Any] = field(default_factory=dict)
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=utc_now)


@dataclass
class TaskStep:
    step_id: str
    capability: str
    dependencies: list[str] = field(default_factory=list)
    status: str = StepStatus.PENDING
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.step_id:
            raise ValueError("step_id is required")
        if not self.capability:
            raise ValueError("capability is required")
        if self.status not in StepStatus.ALL:
            raise ValueError(f"Unsupported step status: {self.status}")
        if self.step_id in self.dependencies:
            raise ValueError("A step cannot depend on itself")

    def to_dict(self):
        return {
            "step_id": self.step_id,
            "capability": self.capability,
            "dependencies": list(self.dependencies),
            "status": self.status,
            "context": dict(self.context),
        }
