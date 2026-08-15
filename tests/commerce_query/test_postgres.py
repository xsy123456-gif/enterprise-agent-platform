"""PostgreSQL integration tests for the canonical commerce store.

Skipped unless ``COMMERCE_TEST_DATABASE_URL`` is set, mirroring the memory
integration test convention.
"""

import os
import uuid

import pytest

from app.commerce.domain import (
    ExternalIdentity,
    InventorySnapshot,
    MetricSeries,
    Product,
    SKU,
    Store,
)
from app.commerce.query.service import CommerceQueryService
from app.commerce.repositories.errors import TenantIsolationViolation
from app.commerce.repositories.factory import build_identity_map, build_repository

pytestmark = pytest.mark.skipif(
    not os.getenv("COMMERCE_TEST_DATABASE_URL"),
    reason="COMMERCE_TEST_DATABASE_URL is not configured",
)

TABLES = [
    "commerce_inventory_snapshots",
    "commerce_review_insights",
    "commerce_reviews",
    "commerce_search_terms",
    "commerce_keywords",
    "commerce_ad_promoted_items",
    "commerce_ads",
    "commerce_ad_groups",
    "commerce_campaigns",
    "commerce_metric_series",
    "commerce_listing_items",
    "commerce_listings",
    "commerce_skus",
    "commerce_products",
    "commerce_stores",
    "commerce_external_identities",
]


@pytest.fixture(scope="module")
def postgres_repository():
    url = os.environ["COMMERCE_TEST_DATABASE_URL"]
    repo = build_repository(url, initialize=True)
    yield repo


@pytest.fixture(scope="module")
def postgres_identity_map():
    url = os.environ["COMMERCE_TEST_DATABASE_URL"]
    yield build_identity_map(url)


@pytest.fixture
def tenant():
    return f"commerce-test-{uuid.uuid4().hex}"


@pytest.fixture
def repo(postgres_repository, tenant):
    yield postgres_repository
    _cleanup(postgres_repository, tenant)


def _cleanup(repository, tenant_id):
    with repository.connection_factory() as conn:
        with conn.cursor() as cursor:
            for table in TABLES:
                cursor.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))


def _store(tenant):
    return Store(
        store_id="store_amazon_001", tenant_id=tenant, platform="amazon",
        marketplace="US", external_store_id="ext1", name="Amazon001",
        currency="USD", timezone="UTC",
    )


def _metric(tenant, metric_record_id="mr1", value=100.0, period_start="2026-08-01",
            period_end="2026-08-02"):
    return MetricSeries(
        metric_record_id=metric_record_id, tenant_id=tenant, subject_type="STORE",
        subject_id="store_amazon_001", metric_name="GMV", metric_class="AGGREGATED",
        granularity="DAILY", period_start=period_start, period_end=period_end,
        value=value, unit="USD",
    )


def test_schema_validates(postgres_repository):
    info = postgres_repository.validate_schema()
    assert "commerce_stores" in info["tables"]


def test_store_roundtrip(repo, tenant):
    repo.upsert_store(tenant, _store(tenant))
    assert repo.get_store(tenant, "store_amazon_001").name == "Amazon001"


def test_metric_natural_key_idempotent(repo, tenant):
    first = repo.upsert_metric(tenant, _metric(tenant, "mr1", 100.0))
    second = repo.upsert_metric(tenant, _metric(tenant, "mr2", 150.0))
    assert first.metric_record_id == "mr1"
    assert second.metric_record_id == "mr1"
    assert second.value == 150.0
    rows = repo.query_metrics(tenant, "STORE", "store_amazon_001", ["GMV"], "DAILY")
    assert len(rows) == 1


def test_inventory_append_semantics(repo, tenant):
    repo.upsert_store(tenant, _store(tenant))
    repo.upsert_product(tenant, Product(product_id="p1", tenant_id=tenant, title="x"))
    repo.upsert_sku(tenant, SKU(sku_id="s1", tenant_id=tenant, product_id="p1",
                                merchant_sku="m"))
    snap = InventorySnapshot(
        inventory_snapshot_id="inv1", tenant_id=tenant, store_id="store_amazon_001",
        sku_id="s1", available_quantity=10, snapshot_at="2026-08-01T00:00:00+00:00",
        source_metadata={"source": "amazon"},
    )
    assert repo.append_inventory_snapshot(tenant, snap) is True
    assert repo.append_inventory_snapshot(tenant, snap) is False
    assert repo.get_latest_inventory(tenant, "store_amazon_001", "s1").available_quantity == 10


def test_tenant_isolation(repo, tenant):
    repo.upsert_store(tenant, _store(tenant))
    other = f"{tenant}-other"
    with pytest.raises(TenantIsolationViolation):
        repo.upsert_store(other, _store(tenant))
    assert repo.get_store(other, "store_amazon_001") is None
    assert repo.list_stores(other) == []


def test_external_identity_map_stable(postgres_identity_map, repo, tenant):
    ext = ExternalIdentity(
        tenant_id=tenant, platform="amazon", store_id="store_amazon_001",
        resource_type="PRODUCT", external_id="ASIN1", canonical_id="product_000021",
    )
    assert postgres_identity_map.register(tenant, ext) == "product_000021"
    ext2 = ExternalIdentity(
        tenant_id=tenant, platform="amazon", store_id="store_amazon_001",
        resource_type="PRODUCT", external_id="ASIN1", canonical_id="product_999",
    )
    assert postgres_identity_map.register(tenant, ext2) == "product_000021"
    assert postgres_identity_map.resolve(
        tenant, "amazon", "store_amazon_001", "PRODUCT", "ASIN1"
    ) == "product_000021"


def test_query_service_end_to_end(repo, tenant):
    repo.upsert_store(tenant, _store(tenant))
    service = CommerceQueryService(repo)
    result = service.get_store(tenant, "store_amazon_001")
    assert result.page.returned_count == 1
    assert result.freshness.status == "FRESH"
    assert result.effective_scope == {"tenant_id": tenant}
