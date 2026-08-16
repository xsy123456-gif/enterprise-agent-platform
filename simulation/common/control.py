"""Failure injection control (Phase 18.13.1).

Deterministic failure injection for tests: fail-next (503), rate-limit-next
(429 + Retry-After), delay-next (simulate a slow provider), and malformed-next
(HTTP 200 with a broken body).  Controlled via ``/__simulation__/control/*`` or
in-process by tests; never part of the provider product contract.
"""

import threading


class FailureInjector:
    def __init__(self):
        self._lock = threading.Lock()
        self.fail_next = 0
        self.rate_limit_next = 0
        self.retry_after = 1
        self.delay_seconds = 0.0
        self.malformed_next = 0

    def fail_next_request(self, count=1):
        with self._lock:
            self.fail_next += count

    def rate_limit_next_request(self, count=1, retry_after=1):
        with self._lock:
            self.rate_limit_next += count
            self.retry_after = retry_after

    def delay_next_request(self, seconds):
        with self._lock:
            self.delay_seconds = seconds

    def malformed_next_request(self, count=1):
        with self._lock:
            self.malformed_next += count

    def reset(self):
        with self._lock:
            self.fail_next = 0
            self.rate_limit_next = 0
            self.retry_after = 1
            self.delay_seconds = 0.0
            self.malformed_next = 0

    def take(self):
        """Consume the next injected action, or return None."""
        with self._lock:
            if self.fail_next > 0:
                self.fail_next -= 1
                return ("fail", None)
            if self.rate_limit_next > 0:
                self.rate_limit_next -= 1
                return ("rate_limit", self.retry_after)
            if self.delay_seconds > 0:
                seconds = self.delay_seconds
                self.delay_seconds = 0.0
                return ("delay", seconds)
            if self.malformed_next > 0:
                self.malformed_next -= 1
                return ("malformed", None)
            return None


__all__ = ["FailureInjector"]
