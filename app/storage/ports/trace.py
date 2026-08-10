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

    @abstractmethod
    def update_trace(self, trace: ExecutionTrace) -> None:
        raise NotImplementedError

    @abstractmethod
    def append_span(self, span) -> None:
        raise NotImplementedError

    @abstractmethod
    def update_span(self, span) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_spans(self, trace_id: str) -> tuple:
        raise NotImplementedError

    @abstractmethod
    def append_event(self, event) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_events(self, trace_id: str) -> tuple:
        raise NotImplementedError
