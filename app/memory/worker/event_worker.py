from datetime import datetime, timezone
from queue import Queue
from threading import Thread

from app.memory.models.event import MemoryEventStatus
from app.memory.events import MemoryDomainEvent


class MemoryWorker:
    """Process Memory-owned inbox events; it has no knowledge of platform events."""

    def __init__(self, repository, write_pipeline, event_sink=None, async_mode=True):
        self.repository = repository
        self.write_pipeline = write_pipeline
        self.async_mode = async_mode
        self.event_sink = event_sink
        self.queue = Queue()
        self.worker = None
        if async_mode:
            self.worker = Thread(target=self._run, name="memory-worker", daemon=True)
            self.worker.start()

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
            if self.event_sink:
                self.event_sink.publish(MemoryDomainEvent(
                    event_type="memory.failed", aggregate_id=event.event_id,
                    payload={"trace_id": event.trace_id, "task_id": event.task_id,
                             "agent_id": event.agent_id, "error": str(error)},
                ))
        event.processed_at = datetime.now(timezone.utc)
        self.repository.update_event(event)
