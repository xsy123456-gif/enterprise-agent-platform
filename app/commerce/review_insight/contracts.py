"""ReviewInsight extraction contract (Phase 11).

``ReviewExtractorPort`` is the provider-neutral boundary: a provider adapter
maps a batch of ``ReviewInput`` into canonical ``ReviewExtractionResult``.  A
provider must never return a ``ReviewInsight`` — provenance is stamped by the
Service.
"""

from abc import ABC, abstractmethod

from app.commerce.review_insight.domain import (
    ReviewExtractionBatchResult,
    ReviewInput,
)


class ReviewExtractorPort(ABC):
    @abstractmethod
    def extract_batch(self, reviews, context=None) -> ReviewExtractionBatchResult:
        """Extract a batch of reviews into canonical results.

        ``reviews`` is an iterable of ``ReviewInput``; ``context`` is an
        optional ``KnowledgeContext`` (never returned in results).
        """
        pass


__all__ = ["ReviewExtractorPort"]
