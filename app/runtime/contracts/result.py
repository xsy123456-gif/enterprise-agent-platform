from dataclasses import dataclass, field

from app.runtime.contracts.event import RuntimeEvent
from app.runtime.contracts.state import AgentRuntimeState


@dataclass(frozen=True)
class ExecutionResult:
    task_id: str
    status: str
    response: str | None
    state: AgentRuntimeState
    events: list[RuntimeEvent] = field(default_factory=list)

    def __post_init__(self):
        if not self.task_id or not self.status:
            raise ValueError("ExecutionResult task_id and status are required")
        if self.task_id != self.state.task_id:
            raise ValueError("ExecutionResult task_id must match Runtime state")

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "status": self.status,
            "response": self.response,
            "state": self.state.to_dict(),
            "events": [event.to_dict() for event in self.events],
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        data["state"] = AgentRuntimeState.from_dict(data["state"])
        data["events"] = [RuntimeEvent.from_dict(item) for item in data.get("events", [])]
        return cls(**data)
