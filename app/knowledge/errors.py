"""Knowledge subsystem exceptions.

Platform-facing only.  Backend/provider native errors (Qdrant, Haystack,
embedding providers) must never leak past this boundary.
"""


class KnowledgeError(Exception):
    """Base class for all Knowledge subsystem errors."""


class KnowledgeInvalidRequestError(KnowledgeError):
    """A retrieve/ingest request failed validation."""


class KnowledgeValidationError(KnowledgeError):
    """A source document or ACL metadata failed validation."""


class KnowledgeAccessDeniedError(KnowledgeError):
    """The effective scope resolved to an empty authorized set."""


class KnowledgeUnavailableError(KnowledgeError):
    """The knowledge backend (e.g. Qdrant) is unreachable."""


class KnowledgeEmbeddingError(KnowledgeError):
    """The embedding provider failed."""


class KnowledgeRetrievalError(KnowledgeError):
    """A retrieval step failed."""


class KnowledgeTimeoutError(KnowledgeError):
    """A retrieval/ingestion step exceeded its configured timeout."""


class KnowledgeNotFoundError(KnowledgeError):
    """A referenced document/chunk does not exist."""


class KnowledgeVersionConflictError(KnowledgeError):
    """A document version transition is invalid."""


class KnowledgeIngestionError(KnowledgeError):
    """A knowledge ingestion step failed."""


class KnowledgeIndexError(KnowledgeError):
    """An indexing/reindex operation failed."""
