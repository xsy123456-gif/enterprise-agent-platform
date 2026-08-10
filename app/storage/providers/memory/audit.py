from copy import deepcopy
from threading import RLock
from typing import Any, Mapping

from app.storage.exceptions import ConflictError
from app.storage.ports.audit import AuditRepository


class InMemoryAuditRepository(AuditRepository):
    def __init__(self):
        self._records: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def write(self, record: Mapping[str, Any]) -> None:
        stored = deepcopy(dict(record))
        audit_id = stored.get("audit_id")
        if not isinstance(audit_id, str) or not audit_id:
            raise ValueError("audit record requires a non-empty audit_id")
        with self._lock:
            if audit_id in self._records:
                raise ConflictError(f"Audit record already exists: {audit_id}")
            self._records[audit_id] = stored

    def query(self, **filters: Any) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(
                deepcopy(record)
                for record in self._records.values()
                if all(record.get(name) == value for name, value in filters.items())
            )

    def export(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(deepcopy(record) for record in self._records.values())
