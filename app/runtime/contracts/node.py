from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.runtime.contracts.event import RuntimeEvent
from app.runtime.contracts.state import AgentRuntimeState, serialize_value


class NodeType(str, Enum):
    START = "START"
    END = "END"
    AGENT = "AGENT"
    TOOL = "TOOL"
    MEMORY = "MEMORY"
    GOVERNANCE = "GOVERNANCE"
    SUPERVISOR = "SUPERVISOR"
    SUBGRAPH = "SUBGRAPH"
    HUMAN = "HUMAN"


@dataclass(frozen=True)
class NodeResult:
    status: str
    state_patch: dict[str, Any] = field(default_factory=dict)
    events: list[RuntimeEvent] = field(default_factory=list)
    error: str | None = None

    def __post_init__(self):
        if not self.status:
            raise ValueError("NodeResult status is required")

    def to_dict(self):
        return {
            "status": self.status,
            "state_patch": serialize_value(self.state_patch),
            "events": [event.to_dict() for event in self.events],
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        data["events"] = [RuntimeEvent.from_dict(item) for item in data.get("events", [])]
        return cls(**data)


class NodeContract(ABC):
    @abstractmethod
    def execute(self, state: AgentRuntimeState) -> NodeResult:
        pass
