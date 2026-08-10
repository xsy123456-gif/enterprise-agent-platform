from concurrent.futures import ThreadPoolExecutor, wait
from threading import RLock

from app.runtime.governance.events import RuntimeEvent
from .event_adapter import MemoryEventAdapter


class AsyncMemoryEventConsumer:
    """Non-blocking EventBus consumer delegating writes to Memory's public API."""

    def __init__(self, memory, event_adapter=None, event_bus=None, event_store=None):
        self.memory = memory
        self.event_adapter = event_adapter or MemoryEventAdapter()
        self.event_bus = event_bus
        self.event_store = event_store
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="memory-events")
        self._futures = set()
        self._lock = RLock()

    def handle(self, event):
        if not isinstance(event, RuntimeEvent) or event.event_type != "response.completed":
            return None
        memory_event = self.event_adapter.adapt(event)
        self._emit(event, "memory.write.requested", "requested", {})
        future = self._executor.submit(self._write, event, memory_event)
        with self._lock:
            self._futures.add(future)
        future.add_done_callback(self._discard)
        return future

    def _write(self, source_event, memory_event):
        try:
            request = self.event_adapter.to_write_request(memory_event)
            receipt = self.memory.write(request)
            self._emit(source_event, "memory.write.completed", "completed", {
                "memory_event_id": getattr(receipt, "event_id", None),
                "accepted": getattr(receipt, "accepted", True),
            })
            return receipt
        except Exception as error:
            self._emit(source_event, "memory.write.failed", "failed", {
                "error": str(error),
            })
            return None

    def _emit(self, source, event_type, status, payload):
        event = RuntimeEvent(
            event_type=event_type,
            execution_id=source.execution_id,
            trace_id=source.trace_id,
            agent_id=source.agent_id,
            agent_version=source.agent_version,
            artifact_id=source.artifact_id,
            artifact_hash=source.artifact_hash,
            backend_type=source.backend_type,
            status=status,
            payload=dict(payload),
        )
        if self.event_store is not None:
            self.event_store.append(event)
        if self.event_bus is not None:
            self.event_bus.publish(event)
        return event

    def _discard(self, future):
        with self._lock:
            self._futures.discard(future)

    def drain(self, timeout=None):
        with self._lock:
            futures = tuple(self._futures)
        if futures:
            wait(futures, timeout=timeout)

    def close(self, wait_for_pending=True):
        self._executor.shutdown(wait=wait_for_pending)
