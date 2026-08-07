from dataclasses import dataclass


class MemoryError(Exception):
    pass


class MemoryValidationError(MemoryError):
    pass


class MemoryAccessDenied(MemoryError, PermissionError):
    pass


class MemoryProviderError(MemoryError):
    def __init__(self, message, transient=True):
        super().__init__(message)
        self.transient = transient


class MemoryStorageError(MemoryError):
    pass


class MemoryInvariantViolation(MemoryError):
    pass


class ConcurrentMemoryWrite(MemoryError):
    pass


class MemoryConcurrencyError(MemoryError):
    pass


@dataclass(frozen=True)
class ErrorDisposition:
    code: str
    retryable: bool


_ERROR_TABLE = {
    (PermissionError, MemoryAccessDenied): ErrorDisposition("authorization_denied", False),
    MemoryValidationError:          ErrorDisposition("validation_failed", False),
    MemoryInvariantViolation:       ErrorDisposition("invariant_violation", False),
    MemoryProviderError:            ErrorDisposition("provider_error", True),
    MemoryStorageError:             ErrorDisposition("storage_error", True),
    MemoryConcurrencyError:         ErrorDisposition("concurrency_error", True),
    ConcurrentMemoryWrite:          ErrorDisposition("concurrency_error", True),
}


def classify_error(exc):
    """Map an exception to an ErrorDisposition.

    Matches by isinstance so subclassing works.
    Unknown exceptions get 'unknown_error' / retryable=True.
    """
    for types, disposition in _ERROR_TABLE.items():
        if isinstance(exc, types):
            return disposition
    return ErrorDisposition("unknown_error", True)
