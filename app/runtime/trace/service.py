from concurrent.futures import ThreadPoolExecutor, wait
from threading import RLock

from app.runtime.governance.events import RuntimeEvent


class AsyncTraceConsumer:
    """Failure-isolated EventBus subscriber for observability only."""

    def __init__(self, assembler):
        self.assembler = assembler
        self.errors = []
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="runtime-trace")
        self._futures = set()
        self._lock = RLock()

    def handle(self, event):
        if not isinstance(event, RuntimeEvent):
            return None
        future = self._executor.submit(self._consume, event)
        with self._lock:
            self._futures.add(future)
        future.add_done_callback(self._discard)
        return future

    def _consume(self, event):
        try:
            return self.assembler.consume(event)
        except Exception as error:
            self.errors.append(str(error))
            return None

    def _discard(self, future):
        with self._lock:
            self._futures.discard(future)

    def drain(self, timeout=None):
        with self._lock:
            futures = tuple(self._futures)
        if futures:
            wait(futures, timeout=timeout)

    def close(self):
        self._executor.shutdown(wait=True)


class TraceQueryService:
    def __init__(self, repository):
        self.repository = repository

    def get_trace(self, trace_id):
        return self.repository.get(trace_id)

    def get_by_execution(self, execution_id):
        return self.repository.query(execution_id)

    def span_tree(self, trace_id):
        return self.repository.list_spans(trace_id)

    def timeline(self, trace_id):
        return tuple(
            {
                "timestamp": event.timestamp,
                "event_type": event.event_type,
                "span_id": event.span_id,
                "operation_id": event.operation_id,
                "status": event.status,
                "node_id": event.node_id,
                "attributes": dict(event.payload),
            }
            for event in self.repository.list_events(trace_id)
        )
