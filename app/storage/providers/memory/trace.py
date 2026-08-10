from copy import deepcopy
from threading import RLock

from app.runtime.governance.trace import ExecutionTrace
from app.storage.exceptions import ConflictError, NotFoundError
from app.storage.ports.trace import TraceRepository


class InMemoryTraceRepository(TraceRepository):
    def __init__(self):
        self._records: dict[str, ExecutionTrace] = {}
        self._lock = RLock()

    def append(self, trace: ExecutionTrace) -> None:
        if not isinstance(trace, ExecutionTrace):
            raise TypeError("trace must be an ExecutionTrace")
        with self._lock:
            if trace.trace_id in self._records:
                raise ConflictError(f"Trace already exists: {trace.trace_id}")
            self._records[trace.trace_id] = deepcopy(trace)

    def query(self, execution_id: str) -> tuple[ExecutionTrace, ...]:
        with self._lock:
            return tuple(
                deepcopy(trace)
                for trace in self._records.values()
                if trace.execution_id == execution_id
            )

    def get(self, trace_id: str) -> ExecutionTrace:
        with self._lock:
            try:
                return deepcopy(self._records[trace_id])
            except KeyError as exc:
                raise NotFoundError(f"Trace not found: {trace_id}") from exc
