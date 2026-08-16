"""In-memory idempotency store (Phase 18.12.5)."""

from app.api.idempotency.port import IdempotencyStore


class InMemoryIdempotencyStore(IdempotencyStore):

    def __init__(self):
        self._records = {}

    def get(self, scope, key):
        return self._records.get((tuple(scope), key))

    def put(self, scope, key, record):
        self._records[(tuple(scope), key)] = record
        return record


__all__ = ["InMemoryIdempotencyStore"]
