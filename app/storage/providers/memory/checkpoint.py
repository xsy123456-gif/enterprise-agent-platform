from copy import deepcopy
from threading import RLock
from typing import Any

from app.storage.exceptions import NotFoundError
from app.storage.ports.checkpoint import CheckpointStore


class InMemoryCheckpointStore(CheckpointStore):
    def __init__(self):
        self._states: dict[str, Any] = {}
        self._lock = RLock()

    def save(self, execution_id: str, state: Any) -> None:
        if not execution_id:
            raise ValueError("execution_id is required")
        with self._lock:
            self._states[execution_id] = deepcopy(state)

    def load(self, execution_id: str) -> Any:
        with self._lock:
            try:
                return deepcopy(self._states[execution_id])
            except KeyError as exc:
                raise NotFoundError(f"Checkpoint not found: {execution_id}") from exc

    def delete(self, execution_id: str) -> None:
        with self._lock:
            try:
                del self._states[execution_id]
            except KeyError as exc:
                raise NotFoundError(f"Checkpoint not found: {execution_id}") from exc
