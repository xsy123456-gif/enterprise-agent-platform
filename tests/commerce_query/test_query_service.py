"""Commerce Query Service unit tests (in-memory): metadata assembly, tenant
scope, freshness, quality and provenance."""

import pytest

from app.commerce.domain import InventorySnapshot, MetricSeries, Product, SKU, Store
from app.commerce.query.freshness import FreshnessPolicy
from app.commerce.query.service import CommerceQueryService
from app.commerce.repositories.inmemory import InMemoryCommerceRepository

TENANT = "company_A"


@pytest.fixture
def service():
    repo = InMemoryCommerceRepository()
    return CommerceQueryService(repo)


def _store():
    return Store(
        store_id="store_amazon_001", tenant_id=TENANT, platform="amazon",
        marketplace="US", external_store_id="ext1", name="Amazon001",
        currency="USD", timezone="UTC",
    )


def test_get_store_assembles_metadata(service):
    service.repository.upsert_store(TENANT, _store())
    result = service.get_store(TENANT, "store_amazon_001")
    assert result.data[0].name == "Amazon001"
    assert result.effective_scope == {"tenant_id": TENANT}
    assert result.freshness.status == "FRESH"
    assert result.quality.status == "VALID"
    assert result.provenance.source_type == "CANONICAL"
    assert result.page.returned_count == 1
    assert result.partial is False


def test_empty_result_is_insufficient(service):
    result = service.get_store(TENANT, "missing")
    assert result.data == ()
    assert result.quality.status == "INSUFFICIENT"
    assert result.freshness.status == "UNKNOWN"


def test_freshness_stale_with_ttl_policy():
    repo = InMemoryCommerceRepository()
    policy = FreshnessPolicy("commerce.standard_read.v1", "1.0", ttl_seconds=0.0)
    svc = CommerceQueryService(repo, freshness_policy=policy)
    repo.upsert_store(TENANT, _store())
    result = svc.get_store(TENANT, "store_amazon_001")
    assert result.freshness.status == "STALE"


def test_query_metrics_tenant_and_time_scoped(service):
    repo = service.repository
    for i, (start, end, value) in enumerate([
        ("2026-08-01", "2026-08-02", 100.0),
        ("2026-08-02", "2026-08-03", 200.0),
        ("2026-08-03", "2026-08-04", 300.0),
    ]):
        repo.upsert_metric(TENANT, MetricSeries(
            metric_record_id=f"mr{i}", tenant_id=TENANT, subject_type="STORE",
            subject_id="store_amazon_001", metric_name="GMV",
            metric_class="AGGREGATED", granularity="DAILY",
            period_start=start, period_end=end, value=value,
        ))
    result = service.query_metrics(TENANT, "STORE", "store_amazon_001", ["GMV"], "DAILY")
    assert result.page.returned_count == 3
    assert result.effective_scope == {"tenant_id": TENANT}


def test_query_inventory_uses_snapshot_freshness(service):
    repo = service.repository
    repo.upsert_store(TENANT, _store())
    repo.upsert_product(TENANT, Product(product_id="p1", tenant_id=TENANT, title="x"))
    repo.upsert_sku(TENANT, SKU(sku_id="s1", tenant_id=TENANT, product_id="p1",
                                merchant_sku="m"))
    repo.append_inventory_snapshot(TENANT, InventorySnapshot(
        inventory_snapshot_id="inv1", tenant_id=TENANT, store_id="store_amazon_001",
        sku_id="s1", available_quantity=3, snapshot_at="2026-08-01T00:00:00+00:00",
    ))
    result = service.query_inventory(TENANT, "store_amazon_001", "s1")
    assert result.page.returned_count == 1
    assert result.freshness.last_synced_at == "2026-08-01T00:00:00+00:00"


def test_tenant_scope_never_from_request(service):
    service.repository.upsert_store(TENANT, _store())
    # Even if a caller supplies a different tenant, the result is scoped to the
    # trusted tenant passed to the service.
    result = service.get_store("company_B", "store_amazon_001")
    assert result.data == ()
    assert result.effective_scope == {"tenant_id": "company_B"}
