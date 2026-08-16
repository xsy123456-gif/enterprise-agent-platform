"""Circuit breaker (Phase 15.2).

Protects external dependencies: after ``failure_threshold`` failures the circuit
opens and rejects calls fast (fail-fast), then probes in HALF_OPEN before
closing again.
"""

import time

from app.platform.production.errors import CircuitOpenError

CIRCUIT_CLOSED = "CLOSED"
CIRCUIT_OPEN = "OPEN"
CIRCUIT_HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:

    def __init__(self, failure_threshold=100, recovery_timeout=60.0, clock=None):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._clock = clock or time.monotonic
        self._failures = 0
        self._state = CIRCUIT_CLOSED
        self._opened_at = None

    @property
    def state(self):
        return self._state

    def call(self, fn):
        if self._state == CIRCUIT_OPEN:
            if self._clock() - self._opened_at >= self.recovery_timeout:
                self._state = CIRCUIT_HALF_OPEN
            else:
                raise CircuitOpenError("circuit is open")
        try:
            result = fn()
            self._on_success()
            return result
        except Exception:  # noqa: BLE001 - counted as a failure, re-raised
            self._on_failure()
            raise

    def _on_failure(self):
        self._failures += 1
        if self._state == CIRCUIT_HALF_OPEN:
            self._open()
        elif self._failures >= self.failure_threshold:
            self._open()

    def _on_success(self):
        self._failures = 0
        if self._state == CIRCUIT_HALF_OPEN:
            self._state = CIRCUIT_CLOSED

    def _open(self):
        self._state = CIRCUIT_OPEN
        self._opened_at = self._clock()


__all__ = ["CircuitBreaker", "CIRCUIT_CLOSED", "CIRCUIT_OPEN", "CIRCUIT_HALF_OPEN"]
