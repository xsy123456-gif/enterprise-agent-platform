from copy import deepcopy
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionCheckpoint:
    execution_id: str
    graph_state: dict
    current_node: str | None = None
    pending_action: dict | None = None
    approval_id: str | None = None


class InMemoryExecutionCheckpointStore:
    """Governance-owned execution checkpoint; independent from Memory storage."""

    def __init__(self):
        self._items = {}

    def save(self, checkpoint: ExecutionCheckpoint):
        self._items[checkpoint.execution_id] = deepcopy(checkpoint)

    def load(self, execution_id: str):
        item = self._items.get(execution_id)
        return deepcopy(item) if item is not None else None

    def delete(self, execution_id: str):
        self._items.pop(execution_id, None)
