"""Sync infrastructure: Raw Landing, Quarantine, Sync Lock/Lease, State store."""

import threading
import uuid
from dataclasses import dataclass, field

from app.commerce.ingestion.envelope import SourceRecordEnvelope
from app.commerce.ingestion.models import SyncCheckpoint, utc_now


class RawLanding:
    """Raw payload landing for replay / adapter debug / audit / recovery (§94)."""

    def __init__(self, retention=None):
        self.retention = retention  # None = keep everything (configurable)
        self.records = []

    def record(self, envelope: SourceRecordEnvelope):
        self.records.append(envelope.to_dict())
        if self.retention is not None and len(self.records) > self.retention:
            self.records = self.records[-self.retention:]

    def list(self):
        return list(self.records)


@dataclass(frozen=True)
class QuarantineRecord:
    sync_run_id: str
    source_record_id: str
    resource: str
    error_code: str
    adapter_version: str
    raw_reference: str
    detected_at: str = field(default_factory=utc_now)


class Quarantine:
    """Adapter/validation failures are quarantined (never ``except: pass``)."""

    def __init__(self):
        self.records = []

    def record(self, record: QuarantineRecord):
        self.records.append(record)

    def list(self):
        return list(self.records)


class SyncLock:
    """Per-partition lock: no concurrent writer for the same
    (tenant, source, store, resource)."""

    def __init__(self):
        self._locks = {}
        self._guard = threading.Lock()

    def acquire(self, partition_key, lease_seconds=300):
        with self._guard:
            if partition_key in self._locks:
                return None
            token = uuid.uuid4().hex
            self._locks[partition_key] = token
            return token

    def release(self, partition_key, token):
        with self._guard:
            if self._locks.get(partition_key) == token:
                del self._locks[partition_key]
                return True
            return False

    def is_locked(self, partition_key):
        with self._guard:
            return partition_key in self._locks


class SyncStateStore:
    """In-memory checkpoint / watermark / last-snapshot-id store."""

    def __init__(self):
        self._states = {}

    def get(self, sync_id) -> SyncCheckpoint:
        return self._states.get(sync_id)

    def save(self, state: SyncCheckpoint):
        self._states[state.sync_id] = state


__all__ = [
    "RawLanding",
    "Quarantine",
    "QuarantineRecord",
    "SyncLock",
    "SyncStateStore",
]
