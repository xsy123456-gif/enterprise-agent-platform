"""ReviewInsight worker repository boundary (Phase 11.2).

``ReviewInsightRepositoryPort`` is the thin, worker-facing persistence port.  It
delegates to the frozen Phase 2 ``CommerceRepository`` — it never re-implements
storage and never exposes raw SQL / connections.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.commerce.domain.review import ReviewInsight


@dataclass(frozen=True)
class ReviewInsightNaturalKey:
    """Idempotency key: tenant + review + extractor id + extractor version."""

    review_id: str
    extractor_id: str
    extractor_version: str


class ReviewInsightRepositoryPort(ABC):
    @abstractmethod
    def save(self, tenant_id, insight: ReviewInsight) -> ReviewInsight:
        pass

    @abstractmethod
    def save_batch(self, tenant_id, insights) -> list[ReviewInsight]:
        pass

    @abstractmethod
    def get_by_id(self, tenant_id, review_insight_id) -> ReviewInsight | None:
        pass

    @abstractmethod
    def list_by_review(self, tenant_id, review_id) -> list[ReviewInsight]:
        pass

    @abstractmethod
    def list_by_listing(self, tenant_id, listing_id) -> list[ReviewInsight]:
        pass

    @abstractmethod
    def exists(self, tenant_id, natural_key: ReviewInsightNaturalKey) -> bool:
        pass


class CanonicalReviewInsightRepository(ReviewInsightRepositoryPort):
    """Delegates every operation to the frozen Phase 2 CommerceRepository."""

    def __init__(self, repository):
        self.repository = repository

    def save(self, tenant_id, insight):
        return self.repository.upsert_review_insight(tenant_id, insight)

    def save_batch(self, tenant_id, insights):
        return [self.save(tenant_id, insight) for insight in insights]

    def get_by_id(self, tenant_id, review_insight_id):
        return self.repository.get_review_insight(tenant_id, review_insight_id)

    def list_by_review(self, tenant_id, review_id):
        return self.repository.list_review_insights_by_review(tenant_id, review_id)

    def list_by_listing(self, tenant_id, listing_id):
        return self.repository.list_review_insights_by_listing(tenant_id, listing_id)

    def exists(self, tenant_id, natural_key):
        return self.repository.exists_review_insight(
            tenant_id, natural_key.review_id, natural_key.extractor_id,
            natural_key.extractor_version,
        )


__all__ = [
    "ReviewInsightNaturalKey",
    "ReviewInsightRepositoryPort",
    "CanonicalReviewInsightRepository",
]
