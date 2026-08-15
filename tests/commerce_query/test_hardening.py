"""Phase 2 Gate Hardening invariants (in-memory).

Covers the three data invariants called out in the Phase 2 gate:

- ``dimensions_hash`` canonical serialization is deterministic regardless of
  dictionary insertion order;
- InventorySnapshot natural key includes source identity, so distinct sources
  for the same (store, sku, snapshot_at) never overwrite each other;
- metric natural-key idempotency holds under dimension reordering and rejects a
  non-canonical caller-supplied hash.
"""

import pytest

from app.commerce.contracts.errors import CommerceValidationError
from app.commerce.domain import InventorySnapshot, MetricSeries, Product, SKU, Store
from app.commerce.domain.metrics import canonical_dimensions_hash
from app.commerce.repositories.inmemory import InMemoryCommerceRepository

TENANT = "company_A"


@pytest.fixture
def repo():
    return InMemoryCommerceRepository()


# ── dimensions_hash canonicalization ─────────────────────────

def test_dimensions_hash_order_independent():
    a = {"channel": "amazon", "marketplace": "US"}
    b = {"marketplace": "US", "channel": "amazon"}
    assert canonical_dimensions_hash(a) == canonical_dimensions_hash(b)


def test_dimensions_hash_nested_dict_order_independent():
    a = {"a": {"x": 1, "y": 2}, "b": [1, 2]}
    b = {"b": [1, 2], "a": {"y": 2, "x": 1}}
    assert canonical_dimensions_hash(a) == canonical_dimensions_hash(b)


def test_dimensions_hash_differs_for_different_values():
    assert canonical_dimensions_hash({"x": 1}) != canonical_dimensions_hash({"x": 2})


def test_metric_same_dimensions_reordered_single_record(repo):
    m1 = MetricSeries(
        metric_record_id="mr1", tenant_id=TENANT, subject_type="STORE",
        subject_id="s1", metric_name="GMV", metric_class="AGGREGATED",
        granularity="DAILY", period_start="2026-08-01", period_end="2026-08-02",
        value=100.0, dimensions={"a": 1, "b": 2},
    )
    m2 = MetricSeries(
        metric_record_id="mr2", tenant_id=TENANT, subject_type="STORE",
        subject_id="s1", metric_name="GMV", metric_class="AGGREGATED",
        granularity="DAILY", period_start="2026-08-01", period_end="2026-08-02",
        value=150.0, dimensions={"b": 2, "a": 1},
    )
    repo.upsert_metric(TENANT, m1)
    second = repo.upsert_metric(TENANT, m2)
    assert second.metric_record_id == "mr1"
    rows = repo.query_metrics(TENANT, "STORE", "s1", ["GMV"], "DAILY")
    assert len(rows) == 1


def test_metric_rejects_non_canonical_dimensions_hash(repo):
    series = MetricSeries(
        metric_record_id="mr1", tenant_id=TENANT, subject_type="STORE",
        subject_id="s1", metric_name="GMV", metric_class="AGGREGATED",
        granularity="DAILY", period_start="2026-08-01", period_end="2026-08-02",
        value=100.0, dimensions={"a": 1}, dimensions_hash="deadbeef",
    )
    with pytest.raises(CommerceValidationError):
        repo.upsert_metric(TENANT, series)


# ── InventorySnapshot source identity ────────────────────────

def _seed_catalog(repo):
    repo.upsert_store(TENANT, Store(
        store_id="store_amazon_001", tenant_id=TENANT, platform="amazon",
        marketplace="US", external_store_id="ext1", name="A1", currency="USD",
        timezone="UTC",
    ))
    repo.upsert_product(TENANT, Product(product_id="p1", tenant_id=TENANT, title="x"))
    repo.upsert_sku(TENANT, SKU(sku_id="s1", tenant_id=TENANT, product_id="p1",
                                merchant_sku="m"))


def test_inventory_distinct_sources_coexist(repo):
    _seed_catalog(repo)
    snap_a = InventorySnapshot(
        inventory_snapshot_id="inv_a", tenant_id=TENANT, store_id="store_amazon_001",
        sku_id="s1", available_quantity=10, snapshot_at="2026-08-01T00:00:00+00:00",
        source_metadata={"source": "amazon"},
    )
    snap_b = InventorySnapshot(
        inventory_snapshot_id="inv_b", tenant_id=TENANT, store_id="store_amazon_001",
        sku_id="s1", available_quantity=7, snapshot_at="2026-08-01T00:00:00+00:00",
        source_metadata={"source": "tiktok"},
    )
    assert repo.append_inventory_snapshot(TENANT, snap_a) is True
    assert repo.append_inventory_snapshot(TENANT, snap_b) is True
    history = repo.list_inventory_history(TENANT, "store_amazon_001", "s1")
    assert sorted(s.inventory_snapshot_id for s in history) == ["inv_a", "inv_b"]


def test_inventory_same_source_is_idempotent(repo):
    _seed_catalog(repo)
    snap = InventorySnapshot(
        inventory_snapshot_id="inv_a", tenant_id=TENANT, store_id="store_amazon_001",
        sku_id="s1", available_quantity=10, snapshot_at="2026-08-01T00:00:00+00:00",
        source_metadata={"source": "amazon"},
    )
    assert repo.append_inventory_snapshot(TENANT, snap) is True
    assert repo.append_inventory_snapshot(TENANT, snap) is False
