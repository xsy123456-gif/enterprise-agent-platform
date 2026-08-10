from dataclasses import dataclass, field
from typing import Any

from app.runtime.contracts.state import AgentRuntimeState, serialize_value
from app.runtime.worker.models import WorkerDefinition


@dataclass(frozen=True)
class WorkerContext:
    runtime_state: AgentRuntimeState
    worker_definition: WorkerDefinition
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "runtime_state": self.runtime_state.to_dict(),
            "worker_definition": self.worker_definition.to_dict(),
            "metadata": serialize_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        data["runtime_state"] = AgentRuntimeState.from_dict(data["runtime_state"])
        data["worker_definition"] = WorkerDefinition.from_dict(
            data["worker_definition"]
        )
        return cls(**data)
