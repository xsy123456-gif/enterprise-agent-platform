"""Business action repository port (Phase 18.10).

``BusinessAction`` is durable business state; its lifecycle (CREATED ->
EXECUTING -> SUCCEEDED/FAILED) must be persisted.  The repository is the
*storage* boundary; ``ActionExecutionPort`` is the *execution* boundary — the
two must never be merged.
"""

from abc import ABC, abstractmethod


class BusinessActionRepository(ABC):
    @abstractmethod
    def put(self, action):
        pass

    @abstractmethod
    def get(self, action_id):
        pass


class InMemoryBusinessActionRepository(BusinessActionRepository):

    def __init__(self):
        self._actions = {}

    def put(self, action):
        self._actions[action.action_id] = action
        return action

    def get(self, action_id):
        return self._actions.get(action_id)


__all__ = ["BusinessActionRepository", "InMemoryBusinessActionRepository"]
