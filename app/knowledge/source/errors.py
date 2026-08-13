"""Knowledge source layer errors."""

from app.knowledge.errors import KnowledgeError


class KnowledgeSourceError(KnowledgeError):
    """Base error for the knowledge source layer."""


class KnowledgeSourceNotFoundError(KnowledgeSourceError):
    """A requested source document does not exist."""


class KnowledgeSourceReadError(KnowledgeSourceError):
    """A source file could not be read or converted."""
