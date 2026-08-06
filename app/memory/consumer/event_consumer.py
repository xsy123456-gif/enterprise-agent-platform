from datetime import datetime, timezone
from queue import Queue
from threading import Thread

from app.memory.api.models import MemoryEventRequest
from app.memory.models.event import MemoryEventStatus


class MemoryEventConsumer:
    """Accepts response events quickly and runs the write pipeline off the response path."""

    def __init__(self, memory_service, repository, write_pipeline, async_mode=True):
        self.memory_service = memory_service
        self.repository = repository
        self.write_pipeline = write_pipeline
        self.async_mode = async_mode
        self.queue = Queue()
        self.memory_service.attach_consumer(self)
        self.worker = None
        if async_mode:
            self.worker = Thread(target=self._run, name="memory-consumer", daemon=True)
            self.worker.start()

    def handle(self, event):
        if getattr(event, "event_type", None) != "response.completed":
            return None
        payload = event.payload
        trace_id = payload.get("trace_id") or "runtime-trace"
        task_id = payload.get("task_id") or trace_id
        request = MemoryEventRequest(
            trace_id=trace_id, task_id=task_id,
            agent_id=payload["agent_id"], user_id=payload["user_id"],
            tenant_id=payload.get("tenant_id") or "default",
            department_id=payload.get("department_id"), event_type="response.completed",
            input={"task": payload.get("input")},
            output=(payload.get("output") if isinstance(payload.get("output"), dict)
                    else {"result": payload.get("output")}),
            tool_results=list(payload.get("tool_results") or []),
            metadata=dict(payload.get("metadata") or {}),
        )
        return self.memory_service.submit(request)

    def enqueue(self, event_id):
        self.queue.put(event_id)
        if not self.async_mode:
            self.process_next()

    def process_next(self):
        event_id = self.queue.get()
        try:
            self._process(event_id)
        finally:
            self.queue.task_done()

    def drain(self):
        self.queue.join()

    def _run(self):
        while True:
            self.process_next()

    def _process(self, event_id):
        event = self.repository.get_event(event_id)
        event.status = MemoryEventStatus.PROCESSING
        self.repository.update_event(event)
        try:
            self.write_pipeline.process(event)
            event.status = MemoryEventStatus.PROCESSED
        except Exception as error:
            event.status = MemoryEventStatus.FAILED
            event.error = str(error)
            publisher = self.write_pipeline.event_publisher
            if publisher:
                publisher("memory.failed", event, {"error": str(error)})
        event.processed_at = datetime.now(timezone.utc)
        self.repository.update_event(event)
