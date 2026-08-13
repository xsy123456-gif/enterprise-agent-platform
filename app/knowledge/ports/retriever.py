"""Knowledge retrieval port — the platform's only dependency on a backend.

The port accepts a trusted ``KnowledgeQuery`` (already validated, authorized and
normalized) and returns a platform-neutral ``KnowledgeRetrieval``.  Backends
(Haystack, LlamaIndex, fakes) implement this port; they never leak their own
types into the platform.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.knowledge.access.filters import EffectiveFilter


@dataclass
class KnowledgeQuery:
    """Trusted internal request produced by KnowledgeService after ACL."""

    query: str
    effective_filter: EffectiveFilter
    top_k: int
    trace_id: str | None = None
    language: str | None = None
    score_threshold: float = 0.0


@dataclass
class RetrievalHit:
    """Platform-neutral retrieval hit; adapter maps backend documents here."""

    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeRetrieval:
    hits: list[RetrievalHit] = field(default_factory=list)
    timing: dict[str, float] = field(default_factory=dict)

    @property
    def empty(self):
        return not self.hits


class KnowledgeRetrieverPort(ABC):
    @abstractmethod
    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeRetrieval:
        raise NotImplementedError
