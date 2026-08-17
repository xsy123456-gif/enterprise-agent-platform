"""Retry framework (Phase 15.2)."""

import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RetryPolicy:
    max_retry: int = 3
    backoff_strategy: str = "exponential"  # "exponential" | "fixed"
    retryable_errors: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, "retryable_errors", tuple(self.retryable_errors or ()))
        if self.backoff_strategy not in ("exponential", "fixed"):
            raise ValueError(f"unknown backoff strategy: {self.backoff_strategy}")


def _is_retryable(error, policy):
    return any(isinstance(error, err) for err in policy.retryable_errors)


def retry_call(fn, policy, sleep=None):
    """Call ``fn`` with retry: retryable errors back off, non-retryable propagate."""
    sleep = sleep or time.sleep
    delay = 1.0
    for attempt in range(policy.max_retry + 1):
        try:
            return fn()
        except Exception as error:  # noqa: BLE001 - classified by policy
            if not _is_retryable(error, policy) or attempt == policy.max_retry:
                raise
            if policy.backoff_strategy == "exponential":
                sleep(delay)
                delay *= 2


__all__ = ["RetryPolicy", "retry_call"]
