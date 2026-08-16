"""ReviewInsight event worker (Phase 11.3).

The worker subscribes to the platform EventBus and turns a
``commerce.review.available`` signal into a governed ``ReviewInsightJob``.  The
Phase 7 ``commerce.data.published`` event (``resource == "review"``) is treated
as the review-available relay; the event payload never carries review content.
"""

from abc import ABC, abstractmethod

from app.commerce.domain.review import Review
from app.commerce.review_insight.domain import RESOURCE_REVIEW, ReviewAvailableEvent

EVENT_DATA_PUBLISHED = "commerce.data.published"
EVENT_REVIEW_AVAILABLE = "commerce.review.available"


class ReviewAccessPort(ABC):
    """Worker-facing read boundary for raw Reviews (never mutated)."""

    @abstractmethod
    def get_reviews(self, tenant_id, review_ids) -> list[Review]:
        pass


class CanonicalReviewAccess(ReviewAccessPort):
    """Delegates to the frozen Phase 2 CommerceRepository.get_review."""

    def __init__(self, repository):
        self.repository = repository

    def get_reviews(self, tenant_id, review_ids):
        reviews = []
        for review_id in review_ids:
            review = self.repository.get_review(tenant_id, review_id)
            if review is not None:
                reviews.append(review)
        return reviews


class ReviewInsightWorker:
    """EventBus subscriber: event -> job -> Service.run_job."""

    def __init__(self, service, job_manager):
        self.service = service
        self.job_manager = job_manager

    def handle(self, event):
        review_event = self._to_review_available(event)
        if review_event is None:
            return None
        job = self.job_manager.create(
            tenant_id=review_event.tenant_id,
            event_id=review_event.event_id,
            review_ids=review_event.review_ids,
            extractor_id=self.service.provenance.extractor_id,
            extractor_version=self.service.provenance.extractor_version,
            trace_id=getattr(event, "trace_id", "") or "",
        )
        return self.service.run_job(job)

    def _to_review_available(self, event):
        if isinstance(event, ReviewAvailableEvent):
            return event if event.resource == RESOURCE_REVIEW else None
        event_type = getattr(event, "event_type", None)
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return None
        if event_type not in (EVENT_DATA_PUBLISHED, EVENT_REVIEW_AVAILABLE):
            return None
        if str(payload.get("resource", "")).upper() != RESOURCE_REVIEW:
            return None
        if not payload.get("review_ids") or not payload.get("tenant_id"):
            return None
        return ReviewAvailableEvent.from_dict({
            "event_id": payload.get("event_id") or payload.get("sync_run_id") or "",
            "tenant_id": payload["tenant_id"],
            "resource": RESOURCE_REVIEW,
            "review_ids": payload.get("review_ids", ()),
            "sync_run_id": payload.get("sync_run_id", ""),
            "published_at": payload.get("published_at", ""),
        })


__all__ = [
    "ReviewAccessPort",
    "CanonicalReviewAccess",
    "ReviewInsightWorker",
    "EVENT_DATA_PUBLISHED",
    "EVENT_REVIEW_AVAILABLE",
]
