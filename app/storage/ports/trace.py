from abc import ABC, abstractmethod

from app.runtime.governance.trace import ExecutionTrace


class TraceRepository(ABC):
    """Append-only persistence boundary for execution traces."""

    @abstractmethod
    def append(self, trace: ExecutionTrace) -> None:
        raise NotImplementedError

    @abstractmethod
    def query(self, execution_id: str) -> tuple[ExecutionTrace, ...]:
        raise NotImplementedError

    @abstractmethod
    def get(self, trace_id: str) -> ExecutionTrace:
        raise NotImplementedError
