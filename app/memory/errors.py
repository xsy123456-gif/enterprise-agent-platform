class MemoryError(Exception):
    pass


class MemoryInvariantViolation(MemoryError):
    pass


class ConcurrentMemoryWrite(MemoryError):
    pass


class MemoryConcurrencyError(MemoryError):
    pass
