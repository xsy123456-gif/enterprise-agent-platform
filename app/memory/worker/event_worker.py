from datetime import datetime, timedelta, timezone
from threading import Event, Lock, Thread
import uuid

from app.memory.errors import (
    MemoryAccessDenied, MemoryError, MemoryInvariantViolation, MemoryValidationError,
)
from app.memory.events import MemoryDomainEvent
from app.memory.models.event import MemoryEventStatus


class MemoryWorker:
    """Durable-inbox worker. PostgreSQL is the source of work, never a Queue."""

    def __init__(self, repository, write_pipeline, event_sink=None, worker_id=None,
                 max_attempts=5, lease_seconds=30, poll_interval=0.1,
                 claim_limit=1):
        self.repository = repository
        self.write_pipeline = write_pipeline
        self.event_sink = event_sink
        self.worker_id = worker_id or f"memory-worker-{uuid.uuid4()}"
        self.max_attempts = max_attempts
        self.lease_seconds = lease_seconds
        self.poll_interval = poll_interval
        self.claim_limit = claim_limit
        self._running = Event()
        self._stopped = Event()
        self._thread = None
        self._processing = Lock()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stopped.clear()
        self._running.set()
        self._thread = Thread(target=self._run, name=self.worker_id, daemon=True)
        self._thread.start()

    def stop(self, timeout=None):
        self._running.clear()
        if self._thread:
            self._thread.join(timeout)
        return self._stopped.is_set()

    def drain(self):
        while self.process_once():
            pass

    def health(self):
        return {"worker_id": self.worker_id, "running": self._running.is_set()}

    def process_once(self, limit=None):
        limit = limit or self.claim_limit
        claimed = self.repository.claim_events(
            self.worker_id, limit, self.lease_seconds
        )
        if not claimed:
            self.dispatch_outbox()
            return 0
        for event in claimed:
            self._process(event)
        self.dispatch_outbox()
        return len(claimed)

    def dispatch_outbox(self, limit=100):
        if not self.event_sink:
            return 0
        published = 0
        records = self.repository.claim_outbox(limit, self.worker_id, 30)
        for record in records:
            try:
                event = MemoryDomainEvent(
                    event_id=record["id"],
                    event_type=record["event_type"],
                    aggregate_id=record["aggregate_id"],
                    payload=record["payload"],
                )
                self.event_sink.publish(event)
                self.repository.mark_outbox_published(event.event_id)
                published += 1
            except Exception as error:
                self.repository.retry_outbox(
                    record["id"], str(error),
                    datetime.now(timezone.utc) + timedelta(seconds=1)
                )
        return published

    def _run(self):
        try:
            while self._running.is_set():
                try:
                    if not self.process_once():
                        self._stopped.wait(self.poll_interval)
                except Exception:
                    self._stopped.wait(self.poll_interval)
        finally:
            self._stopped.set()

    def _process(self, event):
        with self._processing:
            lock_token = getattr(event, "lock_token", None)
            try:
                self.write_pipeline.process(event)
                self._renew_lease_if_needed(event.event_id, lock_token)
                domain_events = list(self.write_pipeline.domain_events)
                completed = MemoryDomainEvent(
                    event_type="memory.processing.completed",
                    aggregate_id=event.event_id,
                    payload={"trace_id": event.trace_id,
                             "source_kind": event.source_kind},
                )
                domain_events.append(completed)
                event.status = MemoryEventStatus.PROCESSED
                event.processed_at = datetime.now(timezone.utc)
                self.repository.commit_event_result(event, domain_events, lock_token)
                event.locked_by = None
                event.lease_until = None
                event.lock_token = None
            except (PermissionError, MemoryAccessDenied) as error:
                self._finish_rejected(event, error, "authorization_denied", lock_token)
            except MemoryValidationError as error:
                self._finish_rejected(event, error, "validation_failed", lock_token)
            except MemoryInvariantViolation as error:
                self._finish_dead_letter(event, error, lock_token)
            except Exception as error:
                self._finish_retry_or_dead_letter(event, error, lock_token)

    def _renew_lease_if_needed(self, event_id, lock_token):
        if lock_token:
            self.repository.renew_lease(event_id, lock_token, self.lease_seconds)

    def _finish_rejected(self, event, error, error_code, lock_token):
        event.status = MemoryEventStatus.REJECTED
        event.error_code = error_code
        event.error = str(error)
        event.processed_at = datetime.now(timezone.utc)
        if lock_token:
            try:
                self.repository.commit_event_result(event, [], lock_token)
            except Exception:
                self.repository.update_event(event)
        else:
            self.repository.update_event(event)
        event.locked_by = None
        event.lease_until = None
        event.lock_token = None

    def _finish_dead_letter(self, event, error, lock_token):
        event.status = MemoryEventStatus.DEAD_LETTER
        event.error_code = "invariant_violation"
        event.error = str(error)
        event.processed_at = datetime.now(timezone.utc)
        if lock_token:
            try:
                self.repository.commit_event_result(event, [], lock_token)
            except Exception:
                self.repository.update_event(event)
        else:
            self.repository.update_event(event)
        event.locked_by = None
        event.lease_until = None
        event.lock_token = None

    def _finish_retry_or_dead_letter(self, event, error, lock_token):
        event.error = str(error)
        event.error_code = (
            "provider_error" if isinstance(error, MemoryError) and getattr(error, "transient", False)
            else "storage_error" if isinstance(error, MemoryError)
            else "unknown_error"
        )
        if event.attempt_count >= self.max_attempts:
            event.status = MemoryEventStatus.DEAD_LETTER
            event.processed_at = datetime.now(timezone.utc)
        else:
            event.status = MemoryEventStatus.RETRY_WAIT
            event.next_attempt_at = datetime.now(timezone.utc) + timedelta(
                seconds=min(60, 2 ** max(0, event.attempt_count - 1))
            )
        if lock_token:
            try:
                self.repository.commit_event_result(event, [], lock_token)
            except Exception:
                self.repository.update_event(event)
        else:
            self.repository.update_event(event)
        event.locked_by = None
        event.lease_until = None
        event.lock_token = None
