"""Knowledge reranker port.

The reranker is an optional, internally-replaceable retrieval refinement step.
It must never be exposed to or chosen by the Agent.
"""

from abc import ABC, abstractmethod

from app.knowledge.ports.retriever import RetrievalHit


class KnowledgeRerankerPort(ABC):
    @abstractmethod
    async def rerank(self, query: str, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        """Reorder ``hits`` by relevance to ``query``."""
        raise NotImplementedError
