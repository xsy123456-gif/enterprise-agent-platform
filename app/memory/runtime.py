"""Lifecycle boundary for the Memory worker and event consumer."""

from enum import Enum


class MemoryRuntimeStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


class MemoryRuntimeManager:
    """Owns worker lifecycle without changing Memory read/write semantics."""

    def __init__(self, worker):
        self._worker = worker
        self._status = MemoryRuntimeStatus.STOPPED

    @property
    def running(self):
        return self._status is MemoryRuntimeStatus.RUNNING

    @property
    def status(self):
        return self._status.value

    def start(self):
        if self.running:
            return False
        self._status = MemoryRuntimeStatus.STARTING
        try:
            self._worker.start()
        except Exception:
            self._status = MemoryRuntimeStatus.STOPPED
            raise
        self._status = MemoryRuntimeStatus.RUNNING
        return True

    def stop(self, timeout=None):
        if self._status is MemoryRuntimeStatus.STOPPED:
            return False
        self._status = MemoryRuntimeStatus.STOPPING
        stopped = self._worker.stop(timeout)
        if stopped:
            self._status = MemoryRuntimeStatus.STOPPED
        return stopped

    def health(self):
        result = dict(self._worker.health())
        result["status"] = self.status
        return result

    @property
    def connection_factory(self):
        return getattr(self._worker.repository, "connection_factory", None)
