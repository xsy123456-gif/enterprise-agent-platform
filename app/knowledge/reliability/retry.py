"""Bounded retry with exponential backoff + jitter.

Only transient errors are retryable; authorization/validation/version errors
must never be retried.
"""

import random
import time

RETRYABLE_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    OSError,
)


def is_retryable(error: Exception) -> bool:
    from app.knowledge.errors import KnowledgeUnavailableError, KnowledgeTimeoutError

    if isinstance(error, (KnowledgeUnavailableError, KnowledgeTimeoutError)):
        return True
    return isinstance(error, RETRYABLE_EXCEPTIONS)


def retry_with_backoff(
    callable_fn,
    max_retries=2,
    base_delay=0.05,
    jitter=0.1,
    on_retry=None,
):
    """Execute ``callable_fn`` with bounded exponential backoff."""
    attempt = 0
    while True:
        try:
            return callable_fn()
        except Exception as error:
            if not is_retryable(error) or attempt >= max_retries:
                raise
            attempt += 1
            delay = base_delay * (2 ** (attempt - 1))
            delay = delay + random.uniform(0, jitter)
            if on_retry is not None:
                on_retry(attempt, error)
            time.sleep(delay)
