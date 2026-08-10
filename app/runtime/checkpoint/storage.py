from threading import RLock

from app.runtime.checkpoint.base import CheckpointStore
from app.runtime.contracts import AgentRuntimeState


class InMemoryCheckpointStore(CheckpointStore):
    def __init__(self):
        self._states = {}
        self._lock = RLock()

    def save(self, execution_id, state):
        if not execution_id:
            raise ValueError("execution_id is required")
        if not isinstance(state, AgentRuntimeState):
            raise TypeError("checkpoint state must be AgentRuntimeState")
        with self._lock:
            self._states[execution_id] = state.to_dict()
        return state

    def load(self, execution_id):
        with self._lock:
            payload = self._states.get(execution_id)
            return AgentRuntimeState.from_dict(payload) if payload is not None else None

    def delete(self, execution_id):
        with self._lock:
            payload = self._states.pop(execution_id, None)
            return AgentRuntimeState.from_dict(payload) if payload is not None else None
