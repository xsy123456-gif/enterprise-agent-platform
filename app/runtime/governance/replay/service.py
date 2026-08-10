from abc import ABC, abstractmethod

from .models import BackendComparison, ReplayRecord


class ReplayService(ABC):
    """Replay orchestration contract; v0.8.3 intentionally has no implementation."""

    @abstractmethod
    def create(self, execution_id: str) -> ReplayRecord:
        raise NotImplementedError

    @abstractmethod
    def load(self, record_id: str) -> ReplayRecord:
        raise NotImplementedError

    @abstractmethod
    def compare(
        self,
        execution_id: str,
        backend_a: str,
        backend_b: str,
    ) -> BackendComparison:
        raise NotImplementedError
