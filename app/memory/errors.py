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
