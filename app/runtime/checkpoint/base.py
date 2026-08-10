from abc import ABC, abstractmethod

from app.runtime.contracts import AgentRuntimeState


class CheckpointStore(ABC):
    @abstractmethod
    def save(self, execution_id: str, state: AgentRuntimeState):
        pass

    @abstractmethod
    def load(self, execution_id: str) -> AgentRuntimeState | None:
        pass

    @abstractmethod
    def delete(self, execution_id: str):
        pass
