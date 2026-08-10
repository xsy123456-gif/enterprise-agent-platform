from abc import ABC, abstractmethod
from typing import Any


class CheckpointStore(ABC):
    """Runtime recovery state boundary; it is not a Memory repository."""

    @abstractmethod
    def save(self, execution_id: str, state: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def load(self, execution_id: str) -> Any:
        raise NotImplementedError

    @abstractmethod
    def delete(self, execution_id: str) -> None:
        raise NotImplementedError
