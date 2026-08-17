"""Sync infrastructure: Raw Landing, Quarantine, Sync Lock/Lease, State store."""

import threading
import time
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


@dataclass(frozen=True)
class Lease:
    partition_key: str
    token: str
    owner: str
    expires_at: float


class SyncLock:
    """Per-partition lease: no concurrent writer for the same
    (tenant, source, store, resource).  Leases expire; an expired lease can be
    re-acquired, and a stale owner/token can neither renew, release, nor publish
    a new lease."""

    def __init__(self, clock=None):
        self._clock = clock or time.monotonic
        self._leases = {}
        self._guard = threading.Lock()

    def acquire(self, partition_key, owner="default", lease_seconds=300):
        now = self._clock()
        with self._guard:
            existing = self._leases.get(partition_key)
            if existing is not None and existing.expires_at > now:
                return None
            lease = Lease(partition_key, uuid.uuid4().hex, owner,
                          now + lease_seconds)
            self._leases[partition_key] = lease
            return lease

    def renew(self, partition_key, token, lease_seconds=300):
        now = self._clock()
        with self._guard:
            lease = self._leases.get(partition_key)
            if lease is None or lease.token != token:
                return False
            if lease.expires_at <= now:
                return False
            self._leases[partition_key] = Lease(
                partition_key, token, lease.owner, now + lease_seconds,
            )
            return True

    def release(self, partition_key, token):
        with self._guard:
            lease = self._leases.get(partition_key)
            if lease is None or lease.token != token:
                return False
            del self._leases[partition_key]
            return True

    def is_locked(self, partition_key):
        now = self._clock()
        with self._guard:
            lease = self._leases.get(partition_key)
            return lease is not None and lease.expires_at > now


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
    "Lease",
    "SyncLock",
    "SyncStateStore",
]
