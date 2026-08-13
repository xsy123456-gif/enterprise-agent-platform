"""Enterprise Knowledge / RAG subsystem.

Public surface is intentionally minimal: ``KnowledgeService.retrieve`` is the
only entrypoint Agents may use.  Haystack/Qdrant are implementation details
behind ``KnowledgeRetrieverPort`` and never appear in this package.
"""

from app.knowledge.api.service import KnowledgeService
from app.knowledge.config import KnowledgeConfig
from app.knowledge.errors import (
    KnowledgeAccessDeniedError,
    KnowledgeEmbeddingError,
    KnowledgeError,
    KnowledgeInvalidRequestError,
    KnowledgeNotFoundError,
    KnowledgeTimeoutError,
    KnowledgeUnavailableError,
    KnowledgeVersionConflictError,
)
from app.knowledge.factory import KnowledgeSystem, build_knowledge
from app.knowledge.models.access import KnowledgeAccessContext
from app.knowledge.models.evidence import Citation, RetrievalEvidence
from app.knowledge.models.request import KnowledgeRetrieveRequest
from app.knowledge.models.result import (
    KnowledgeItem,
    KnowledgeRetrieveResult,
)
from app.knowledge.ports.retriever import (
    KnowledgeQuery,
    KnowledgeRetrieval,
    KnowledgeRetrieverPort,
    RetrievalHit,
)

__all__ = [
    "KnowledgeService",
    "KnowledgeConfig",
    "KnowledgeSystem",
    "build_knowledge",
    "KnowledgeAccessContext",
    "KnowledgeRetrieveRequest",
    "KnowledgeRetrieveResult",
    "KnowledgeItem",
    "Citation",
    "RetrievalEvidence",
    "KnowledgeQuery",
    "KnowledgeRetrieval",
    "KnowledgeRetrieverPort",
    "RetrievalHit",
    "KnowledgeError",
    "KnowledgeInvalidRequestError",
    "KnowledgeAccessDeniedError",
    "KnowledgeUnavailableError",
    "KnowledgeEmbeddingError",
    "KnowledgeTimeoutError",
    "KnowledgeNotFoundError",
    "KnowledgeVersionConflictError",
]
