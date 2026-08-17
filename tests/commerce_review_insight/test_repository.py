"""Phase 11.2 Repository + Service tests (in-memory)."""

import pytest

from app.commerce.domain import Listing, Review, Store
from app.commerce.repositories.inmemory import InMemoryCommerceRepository
from app.commerce.review_insight import (
    CanonicalReviewInsightRepository,
    ExtractionError,
    ReviewInsightNaturalKey,
    ReviewInsightProvenance,
    ReviewInsightService,
)
from app.commerce.review_insight.domain import ReviewExtractionResult

TENANT = "company_A"
OTHER_TENANT = "company_B"
REVIEW_ID = "rev1"
LISTING_ID = "listing_1"


def _seed_review(repository, tenant=TENANT):
    repository.upsert_store(tenant, Store(
        store_id="JP01", tenant_id=tenant, platform="amazon", marketplace="JP",
        external_store_id="ext", name="JP01", currency="JPY", timezone="Asia/Tokyo",
    ))
    repository.upsert_listing(tenant, Listing(
        listing_id=LISTING_ID, tenant_id=tenant, store_id="JP01",
        platform="amazon", external_listing_id="B0",
    ))
    repository.upsert_review(tenant, Review(
        review_id=REVIEW_ID, tenant_id=tenant, store_id="JP01",
        listing_id=LISTING_ID, platform="amazon", external_review_id="R1",
        rating=2.0, content="battery died after a week",
    ))


def _provenance(version="1.0"):
    return ReviewInsightProvenance(
        extractor_id="review_extractor", extractor_version=version,
        model_provider="deepseek", model_version="v3", prompt_version="2",
    )


def _result():
    return ReviewExtractionResult(
        review_id=REVIEW_ID, sentiment="negative", issues=("BATTERY_FAILURE",),
        confidence=0.91,
    )


@pytest.fixture
def repo():
    repository = InMemoryCommerceRepository()
    _seed_review(repository)
    return repository


@pytest.fixture
def service(repo):
    return ReviewInsightService(
        CanonicalReviewInsightRepository(repo), _provenance(),
    )


# ── Domain mapping ──────────────────────────────────────────

def test_domain_mapping(repo, service):
    insight = service.submit_extraction_result(TENANT, _result())
    assert insight.review_id == REVIEW_ID
    assert insight.issues == ("BATTERY_FAILURE",)
    assert insight.confidence == 0.91
    # provenance stamped by the service, not the provider
    assert insight.extractor_id == "review_extractor"
    assert insight.extractor_version == "1.0"
    assert insight.model_provider == "deepseek"
    assert insight.prompt_version == "2"
    assert not hasattr(insight, "cause")
    assert not hasattr(insight, "impact")
    assert not hasattr(insight, "priority")


# ── Idempotency ─────────────────────────────────────────────

def test_idempotent_submit(repo, service):
    first = service.submit_extraction_result(TENANT, _result())
    second = service.submit_extraction_result(TENANT, _result())
    assert first.review_insight_id == second.review_insight_id
    assert len(repo.list_review_insights_by_review(TENANT, REVIEW_ID)) == 1


def test_exists(repo, service):
    service.submit_extraction_result(TENANT, _result())
    key = ReviewInsightNaturalKey(REVIEW_ID, "review_extractor", "1.0")
    assert service.repository.exists(TENANT, key) is True
    missing = ReviewInsightNaturalKey(REVIEW_ID, "review_extractor", "9.0")
    assert service.repository.exists(TENANT, missing) is False


# ── Version coexistence ─────────────────────────────────────

def test_version_coexistence(repo):
    service_v1 = ReviewInsightService(
        CanonicalReviewInsightRepository(repo), _provenance("1.0"),
    )
    service_v2 = ReviewInsightService(
        CanonicalReviewInsightRepository(repo), _provenance("2.0"),
    )
    a = service_v1.submit_extraction_result(TENANT, _result())
    b = service_v2.submit_extraction_result(TENANT, _result())
    assert a.review_insight_id != b.review_insight_id
    insights = repo.list_review_insights_by_review(TENANT, REVIEW_ID)
    assert {i.extractor_version for i in insights} == {"1.0", "2.0"}
    assert len(insights) == 2


# ── Tenant isolation ────────────────────────────────────────

def test_tenant_isolation(repo, service):
    insight = service.submit_extraction_result(TENANT, _result())
    key = ReviewInsightNaturalKey(REVIEW_ID, "review_extractor", "1.0")
    assert repo.get_review_insight(OTHER_TENANT, insight.review_insight_id) is None
    assert repo.list_review_insights_by_review(OTHER_TENANT, REVIEW_ID) == []
    assert service.repository.exists(OTHER_TENANT, key) is False


# ── Round trip ──────────────────────────────────────────────

def test_round_trip(repo, service):
    submitted = service.submit_extraction_result(TENANT, _result())
    read = repo.get_review_insight(TENANT, submitted.review_insight_id)
    assert read == submitted


def test_list_by_listing(repo, service):
    insight = service.submit_extraction_result(TENANT, _result())
    listed = repo.list_review_insights_by_listing(TENANT, LISTING_ID)
    assert [i.review_insight_id for i in listed] == [insight.review_insight_id]


# ── Validation ──────────────────────────────────────────────

def test_confidence_out_of_range(repo, service):
    bad = ReviewExtractionResult(review_id=REVIEW_ID, confidence=1.5)
    with pytest.raises(ExtractionError):
        service.submit_extraction_result(TENANT, bad)


def test_confidence_boundary_ok(repo, service):
    for confidence in (0.0, 1.0):
        ok = ReviewExtractionResult(review_id=REVIEW_ID, confidence=confidence)
        service.submit_extraction_result(TENANT, ok)
