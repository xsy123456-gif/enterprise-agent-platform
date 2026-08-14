"""Principal context carrier — durable execution principal binding."""

from abc import ABC, abstractmethod
from threading import RLock

from app.integrations.security.models.execution_context import (
    ExecutionPrincipalBinding,
)


class PrincipalContextCarrierPort(ABC):
    @abstractmethod
    def bind(self, execution_id: str, binding: ExecutionPrincipalBinding) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, execution_id: str) -> ExecutionPrincipalBinding | None:
        raise NotImplementedError

    @abstractmethod
    def remove(self, execution_id: str) -> None:
        raise NotImplementedError


class InMemoryPrincipalContextCarrier(PrincipalContextCarrierPort):
    """Development/testing carrier; production needs a durable store."""

    def __init__(self):
        self._bindings: dict[str, ExecutionPrincipalBinding] = {}
        self._lock = RLock()

    def bind(self, execution_id: str, binding: ExecutionPrincipalBinding) -> None:
        with self._lock:
            self._bindings[execution_id] = binding

    def get(self, execution_id: str) -> ExecutionPrincipalBinding | None:
        with self._lock:
            return self._bindings.get(execution_id)

    def remove(self, execution_id: str) -> None:
        with self._lock:
            self._bindings.pop(execution_id, None)
