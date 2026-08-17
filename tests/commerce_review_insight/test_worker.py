"""Phase 11.3 Worker Runtime tests."""

import pytest

from app.commerce.domain import Listing, Review, Store
from app.commerce.repositories.inmemory import InMemoryCommerceRepository
from app.commerce.review_insight import (
    JOB_CREATED,
    JOB_FAILED,
    JOB_PARTIAL,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    CanonicalReviewAccess,
    CanonicalReviewInsightRepository,
    ExtractorUnavailableError,
    JobNotFoundError,
    ReviewAvailableEvent,
    ReviewExtractionBatchResult,
    ReviewExtractionResult,
    ReviewExtractorPort,
    ReviewInsightJobManager,
    ReviewInsightProvenance,
    ReviewInsightService,
    ReviewInsightWorker,
)
from app.events.models import Event

TENANT = "company_A"
LISTING_ID = "listing_1"


class FakeExtractor(ReviewExtractorPort):
    def __init__(self, unavailable=False, fail_review_ids=(), bad_confidence=()):
        self.unavailable = unavailable
        self.fail_review_ids = set(fail_review_ids)
        self.bad_confidence = set(bad_confidence)

    def extract_batch(self, reviews, context=None):
        if self.unavailable:
            raise ExtractorUnavailableError("provider down")
        results = []
        failed = []
        for review in reviews:
            if review.review_id in self.fail_review_ids:
                failed.append(review.review_id)
                continue
            confidence = 1.5 if review.review_id in self.bad_confidence else 0.9
            results.append(ReviewExtractionResult(
                review_id=review.review_id,
                sentiment="negative" if review.rating <= 2 else "positive",
                confidence=confidence,
            ))
        return ReviewExtractionBatchResult(
            results=tuple(results), failed_review_ids=tuple(failed))


def _seed(repository, tenant=TENANT, review_ids=("rev1", "rev2", "rev3")):
    repository.upsert_store(tenant, Store(
        store_id="JP01", tenant_id=tenant, platform="amazon", marketplace="JP",
        external_store_id="ext", name="JP01", currency="JPY", timezone="Asia/Tokyo",
    ))
    repository.upsert_listing(tenant, Listing(
        listing_id=LISTING_ID, tenant_id=tenant, store_id="JP01",
        platform="amazon", external_listing_id="B0",
    ))
    for review_id in review_ids:
        repository.upsert_review(tenant, Review(
            review_id=review_id, tenant_id=tenant, store_id="JP01",
            listing_id=LISTING_ID, platform="amazon",
            external_review_id=f"ext-{review_id}", rating=2.0,
            title="broken", content="battery issue",
        ))
    return repository


def _provenance():
    return ReviewInsightProvenance(
        extractor_id="review_extractor", extractor_version="1.0",
    )


def _build(repository, extractor):
    manager = ReviewInsightJobManager()
    service = ReviewInsightService(
        CanonicalReviewInsightRepository(repository), _provenance(),
        CanonicalReviewAccess(repository), extractor,
    )
    return ReviewInsightWorker(service, manager), manager


@pytest.fixture
def repo():
    return _seed(InMemoryCommerceRepository())


def _event(review_ids=("rev1", "rev2")):
    return ReviewAvailableEvent(
        event_id="e1", tenant_id=TENANT, review_ids=review_ids,
        sync_run_id="sr1",
    )


# ── Event -> job -> insights ────────────────────────────────

def test_event_consume_creates_job_and_saves_insights(repo):
    worker, manager = _build(repo, FakeExtractor())
    job = worker.handle(_event())
    assert job.status == JOB_SUCCEEDED
    assert job.total_count == 2
    assert job.success_count == 2
    assert job.failed_count == 0
    assert job.extractor_id == "review_extractor"
    assert job.extractor_version == "1.0"
    assert job.event_id == "e1"
    insights = repo.list_review_insights_by_review(TENANT, "rev1")
    assert len(insights) == 1
    assert insights[0].sentiment == "negative"
    assert insights[0].extractor_id == "review_extractor"
    assert len(manager.list_jobs()) == 1


def test_batch_execution_n_reviews(repo):
    worker, _ = _build(repo, FakeExtractor())
    job = worker.handle(_event(("rev1", "rev2", "rev3")))
    assert job.status == JOB_SUCCEEDED
    assert job.success_count == 3
    assert job.total_count == 3
    for review_id in ("rev1", "rev2", "rev3"):
        assert len(repo.list_review_insights_by_review(TENANT, review_id)) == 1


# ── Failure model ───────────────────────────────────────────

def test_partial_single_review_failure(repo):
    worker, _ = _build(repo, FakeExtractor(fail_review_ids={"rev2"}))
    job = worker.handle(_event(("rev1", "rev2", "rev3")))
    assert job.status == JOB_PARTIAL
    assert job.success_count == 2
    assert job.failed_count == 1
    assert len(repo.list_review_insights_by_review(TENANT, "rev1")) == 1
    assert len(repo.list_review_insights_by_review(TENANT, "rev3")) == 1
    assert repo.list_review_insights_by_review(TENANT, "rev2") == []


def test_provider_wide_failure_saves_nothing(repo):
    worker, _ = _build(repo, FakeExtractor(unavailable=True))
    job = worker.handle(_event())
    assert job.status == JOB_FAILED
    assert job.error_summary == "provider down"
    assert job.success_count == 0
    assert repo.list_review_insights_by_review(TENANT, "rev1") == []
    assert repo.list_review_insights_by_review(TENANT, "rev2") == []


def test_invalid_confidence_recorded_not_swallowed(repo):
    worker, _ = _build(repo, FakeExtractor(bad_confidence={"rev2"}))
    job = worker.handle(_event(("rev1", "rev2")))
    assert job.status == JOB_PARTIAL
    assert job.success_count == 1
    assert job.failed_count == 1
    assert "rev2" in job.error_summary
    assert len(repo.list_review_insights_by_review(TENANT, "rev2")) == 0


def test_missing_review_recorded_as_failed(repo):
    worker, _ = _build(repo, FakeExtractor())
    job = worker.handle(_event(("rev1", "ghost")))
    assert job.status == JOB_PARTIAL
    assert job.success_count == 1
    assert job.failed_count == 1


# ── Event filtering / relay ─────────────────────────────────

def test_ignores_non_review_events(repo):
    worker, manager = _build(repo, FakeExtractor())
    result = worker.handle(Event("commerce.data.published", {
        "resource": "listing", "tenant_id": TENANT, "review_ids": ["rev1"],
    }))
    assert result is None
    assert manager.list_jobs() == []


def test_ignores_unrelated_event_types(repo):
    worker, manager = _build(repo, FakeExtractor())
    result = worker.handle(Event("runtime.other", {
        "resource": "REVIEW", "tenant_id": TENANT, "review_ids": ["rev1"],
    }))
    assert result is None
    assert manager.list_jobs() == []


def test_consumes_relayed_data_published(repo):
    worker, _ = _build(repo, FakeExtractor())
    job = worker.handle(Event("commerce.data.published", {
        "resource": "review", "tenant_id": TENANT,
        "review_ids": ["rev1"], "sync_run_id": "sr1", "event_id": "e9",
    }))
    assert job is not None
    assert job.status == JOB_SUCCEEDED
    assert job.event_id == "e9"


# ── Idempotency ─────────────────────────────────────────────

def test_duplicate_events_do_not_duplicate_insights(repo):
    worker, _ = _build(repo, FakeExtractor())
    event = _event(("rev1",))
    worker.handle(event)
    worker.handle(event)
    assert len(repo.list_review_insights_by_review(TENANT, "rev1")) == 1


# ── Job manager ─────────────────────────────────────────────

def test_job_manager_retry_and_cancel(repo):
    worker, manager = _build(repo, FakeExtractor(unavailable=True))
    job = worker.handle(_event(("rev1",)))
    assert job.status == JOB_FAILED
    retried = manager.retry(job.job_id)
    assert retried.retry_count == 1
    assert retried.status == JOB_CREATED
    cancelled = manager.cancel(job.job_id)
    assert cancelled.status == "CANCELLED"


def test_job_manager_get_unknown_raises(repo):
    _, manager = _build(repo, FakeExtractor())
    with pytest.raises(JobNotFoundError):
        manager.get("nope")
