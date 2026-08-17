"""Phase 11.2 Postgres integration tests (gated by COMMERCE_TEST_DATABASE_URL)."""

import os
import uuid

import pytest

from app.commerce.domain import Listing, Review, Store
from app.commerce.repositories.factory import build_repository
from app.commerce.review_insight import (
    CanonicalReviewInsightRepository,
    ReviewInsightNaturalKey,
    ReviewInsightProvenance,
    ReviewInsightService,
)
from app.commerce.review_insight.domain import ReviewExtractionResult

pytestmark = pytest.mark.skipif(
    not os.getenv("COMMERCE_TEST_DATABASE_URL"),
    reason="COMMERCE_TEST_DATABASE_URL is not configured",
)

_TABLES = [
    "commerce_review_insights",
    "commerce_reviews",
    "commerce_listings",
    "commerce_stores",
]


def _cleanup(repository, tenant_id):
    with repository.connection_factory() as conn:
        with conn.cursor() as cursor:
            for table in _TABLES:
                cursor.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))


def _seed(repository, tenant):
    repository.upsert_store(tenant, Store(
        store_id="JP01", tenant_id=tenant, platform="amazon", marketplace="JP",
        external_store_id="ext", name="JP01", currency="JPY", timezone="Asia/Tokyo",
    ))
    repository.upsert_listing(tenant, Listing(
        listing_id="listing_1", tenant_id=tenant, store_id="JP01",
        platform="amazon", external_listing_id="B0",
    ))
    repository.upsert_review(tenant, Review(
        review_id="rev1", tenant_id=tenant, store_id="JP01",
        listing_id="listing_1", platform="amazon", external_review_id="R1",
        rating=2.0, content="battery issue",
    ))


def test_review_insight_postgres_roundtrip_and_idempotency():
    url = os.environ["COMMERCE_TEST_DATABASE_URL"]
    repository = build_repository(url, initialize=True)
    tenant = f"ri-test-{uuid.uuid4().hex}"
    try:
        _seed(repository, tenant)
        service = ReviewInsightService(
            CanonicalReviewInsightRepository(repository),
            ReviewInsightProvenance(extractor_id="review_extractor",
                                    extractor_version="1.0"),
        )
        result = ReviewExtractionResult(
            review_id="rev1", sentiment="negative", issues=("BATTERY_FAILURE",),
            confidence=0.91,
        )
        first = service.submit_extraction_result(tenant, result)
        second = service.submit_extraction_result(tenant, result)
        # idempotent: same canonical record, no duplicate
        assert first.review_insight_id == second.review_insight_id
        assert len(repository.list_review_insights_by_review(tenant, "rev1")) == 1
        # round trip via get
        read = repository.get_review_insight(tenant, first.review_insight_id)
        assert read == first
        assert read.extractor_id == "review_extractor"
        assert read.issues == ("BATTERY_FAILURE",)
        # schema version advanced to 2
        assert repository.schema_version() == 2
    finally:
        _cleanup(repository, tenant)


def test_review_insight_postgres_version_coexistence():
    url = os.environ["COMMERCE_TEST_DATABASE_URL"]
    repository = build_repository(url, initialize=True)
    tenant = f"ri-test-{uuid.uuid4().hex}"
    try:
        _seed(repository, tenant)
        port = CanonicalReviewInsightRepository(repository)
        v1 = ReviewInsightService(port, ReviewInsightProvenance(
            extractor_id="review_extractor", extractor_version="1.0"))
        v2 = ReviewInsightService(port, ReviewInsightProvenance(
            extractor_id="review_extractor", extractor_version="2.0"))
        result = ReviewExtractionResult(review_id="rev1", sentiment="negative")
        a = v1.submit_extraction_result(tenant, result)
        b = v2.submit_extraction_result(tenant, result)
        assert a.review_insight_id != b.review_insight_id
        insights = repository.list_review_insights_by_review(tenant, "rev1")
        assert {i.extractor_version for i in insights} == {"1.0", "2.0"}
        key = ReviewInsightNaturalKey("rev1", "review_extractor", "1.0")
        assert port.exists(tenant, key) is True
    finally:
        _cleanup(repository, tenant)
