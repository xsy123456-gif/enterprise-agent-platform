from copy import deepcopy
from threading import RLock

from app.runtime.governance.trace import ExecutionTrace
from app.storage.exceptions import ConflictError, NotFoundError
from app.storage.ports.trace import TraceRepository


class InMemoryTraceRepository(TraceRepository):
    def __init__(self):
        self._records: dict[str, ExecutionTrace] = {}
        self._spans = {}
        self._events = {}
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

    def update_trace(self, trace):
        with self._lock:
            if trace.trace_id not in self._records:
                raise NotFoundError(f"Trace not found: {trace.trace_id}")
            self._records[trace.trace_id] = deepcopy(trace)

    def append_span(self, span):
        with self._lock:
            spans = self._spans.setdefault(span.trace_id, {})
            if span.span_id in spans:
                raise ConflictError(f"Span already exists: {span.span_id}")
            spans[span.span_id] = deepcopy(span)

    def update_span(self, span):
        with self._lock:
            spans = self._spans.setdefault(span.trace_id, {})
            if span.span_id not in spans:
                raise NotFoundError(f"Span not found: {span.span_id}")
            spans[span.span_id] = deepcopy(span)

    def list_spans(self, trace_id):
        with self._lock:
            return tuple(sorted(
                (deepcopy(item) for item in self._spans.get(trace_id, {}).values()),
                key=lambda item: item.start_time,
            ))

    def append_event(self, event):
        with self._lock:
            events = self._events.setdefault(event.trace_id, {})
            events[event.event_id] = deepcopy(event)

    def list_events(self, trace_id):
        with self._lock:
            return tuple(sorted(
                (deepcopy(item) for item in self._events.get(trace_id, {}).values()),
                key=lambda item: item.timestamp,
            ))
