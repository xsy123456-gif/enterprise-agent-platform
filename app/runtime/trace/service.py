from concurrent.futures import ThreadPoolExecutor, wait
from threading import RLock
from datetime import datetime, timezone

from app.runtime.governance.events import RuntimeEvent


class AsyncTraceConsumer:
    """Failure-isolated EventBus subscriber for observability only."""

    def __init__(self, assembler):
        self.assembler = assembler
        self.errors = []
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="runtime-trace")
        self._futures = set()
        self._lock = RLock()
        self._pending = {}

    def handle(self, event):
        if not isinstance(event, RuntimeEvent) and getattr(event, "event_type", None) not in {
            "tool.called", "tool.completed", "tool.denied", "tool.failed"
        }:
            return None
        future = self._executor.submit(self._consume, event)
        with self._lock:
            self._futures.add(future)
        future.add_done_callback(self._discard)
        return future

    def _consume(self, event):
        try:
            if not isinstance(event, RuntimeEvent):
                normalized = self._normalize_platform_event(event)
                if normalized is None:
                    execution_id = event.payload.get("execution_id")
                    self._pending.setdefault(execution_id, []).append(event)
                    return None
                return self.assembler.consume(normalized)
            result = self.assembler.consume(event)
            pending = self._pending.pop(event.execution_id, [])
            for pending_event in pending:
                normalized = self._normalize_platform_event(pending_event)
                if normalized is not None:
                    self.assembler.consume(normalized)
            return result
        except Exception as error:
            self.errors.append(str(error))
            return None

    def _normalize_platform_event(self, event):
        payload = dict(event.payload)
        trace_id = payload.get("trace_id")
        execution_id = payload.get("execution_id")
        if not trace_id or not execution_id:
            return None
        try:
            trace = self.assembler.repository.get(trace_id)
        except Exception:
            return None
        timestamp = getattr(event, "created_at", None)
        timestamp = datetime.fromisoformat(timestamp) if timestamp else datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return RuntimeEvent(
            event_type=event.event_type, execution_id=execution_id,
            trace_id=trace_id, agent_id=trace.agent_id,
            agent_version=trace.agent_version, artifact_id=trace.artifact_id,
            artifact_hash=trace.artifact_hash, backend_type=trace.backend_type,
            status=event.event_type.rsplit(".", 1)[-1], timestamp=timestamp,
            payload=payload, operation_id=payload.get("request_id"),
        )

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
