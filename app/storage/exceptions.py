class StorageError(Exception):
    """Base exception exposed by cross-domain storage ports."""


class NotFoundError(StorageError):
    """The requested persistent record does not exist."""


class ConflictError(StorageError):
    """The requested write conflicts with an existing immutable record."""


class PersistenceError(StorageError):
    """A provider could not complete a persistence operation."""
