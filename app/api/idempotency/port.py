"""Idempotency store port (Phase 18.12.5)."""

from abc import ABC, abstractmethod


class IdempotencyStore(ABC):
    @abstractmethod
    def get(self, scope, key):
        pass

    @abstractmethod
    def put(self, scope, key, record):
        pass


__all__ = ["IdempotencyStore"]
