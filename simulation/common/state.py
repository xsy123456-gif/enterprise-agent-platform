"""Simulation state store + request log (Phase 18.13.1).

Each provider holds a lock-protected in-memory store of contract fixtures and a
request log.  The request log never records the ``Authorization`` value or any
credential material — only provider/method/path/correlation/status/timestamp.
"""

import threading
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


class RequestLog:
    def __init__(self):
        self._lock = threading.Lock()
        self._entries = []

    def record(self, provider, method, path, correlation_id, status):
        with self._lock:
            self._entries.append({
                "provider": provider,
                "method": method,
                "path": path,
                "correlation_id": correlation_id or "",
                "status": status,
                "timestamp": _now(),
            })

    def list(self):
        with self._lock:
            return list(self._entries)

    def clear(self):
        with self._lock:
            self._entries = []


class ProviderStateStore:
    """In-memory, lock-protected provider records with a resettable baseline."""

    def __init__(self, provider):
        self.provider = provider
        self._lock = threading.Lock()
        self._fixtures = {}
        self._records = {}
        self.request_log = RequestLog()

    def load(self, resource, records):
        """Set the contract fixture baseline for a resource (reset restores it)."""
        with self._lock:
            self._fixtures[resource] = [dict(r) for r in records]
            self._records[resource] = [dict(r) for r in self._fixtures[resource]]

    def list_records(self, resource):
        with self._lock:
            return [dict(r) for r in self._records.get(resource, [])]

    def get(self, resource, id_field, value):
        with self._lock:
            for record in self._records.get(resource, []):
                if record.get(id_field) == value:
                    return dict(record)
            return None

    def upsert(self, resource, id_field, record):
        with self._lock:
            items = self._records.setdefault(resource, [])
            rid = record[id_field]
            for i, existing in enumerate(items):
                if existing.get(id_field) == rid:
                    items[i] = dict(record)
                    return dict(record)
            items.append(dict(record))
            return dict(record)

    def reset(self):
        with self._lock:
            self._records = {
                resource: [dict(r) for r in fixture]
                for resource, fixture in self._fixtures.items()
            }
        self.request_log.clear()


__all__ = ["ProviderStateStore", "RequestLog"]
