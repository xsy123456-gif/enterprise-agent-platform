"""In-memory repository unit tests: CRUD/query, tenant isolation, metric
natural-key idempotency, append-only inventory, external identity stability."""

import pytest

from app.commerce.domain import (
    Ad,
    AdGroup,
    AdPromotedItem,
    Campaign,
    ExternalIdentity,
    InventorySnapshot,
    Keyword,
    Listing,
    ListingItem,
    MetricSeries,
    Product,
    Review,
    ReviewInsight,
    SKU,
    SearchTerm,
    Store,
)
from app.commerce.repositories.errors import (
    CommerceStorageError,
    ExternalIdentityConflict,
    TenantIsolationViolation,
)
from app.commerce.repositories.inmemory import (
    InMemoryCommerceRepository,
    InMemoryExternalIdentityMap,
)

TENANT_A = "company_A"
TENANT_B = "company_B"


@pytest.fixture
def repo():
    return InMemoryCommerceRepository()


@pytest.fixture
def identity_map():
    return InMemoryExternalIdentityMap()


def _store(tenant=TENANT_A, store_id="store_amazon_001"):
    return Store(
        store_id=store_id, tenant_id=tenant, platform="amazon", marketplace="US",
        external_store_id=f"ext-{store_id}", name=store_id, currency="USD",
        timezone="UTC",
    )


def _product(tenant=TENANT_A, product_id="product_000021"):
    return Product(product_id=product_id, tenant_id=tenant, title="Mouse")


def _sku(tenant=TENANT_A, sku_id="sku_000087", product_id="product_000021"):
    return SKU(sku_id=sku_id, tenant_id=tenant, product_id=product_id,
               merchant_sku=f"merch-{sku_id}")


# ── CRUD / query ─────────────────────────────────────────────

def test_store_roundtrip(repo):
    repo.upsert_store(TENANT_A, _store())
    assert repo.get_store(TENANT_A, "store_amazon_001").name == "store_amazon_001"
    assert repo.list_stores(TENANT_A)[0].store_id == "store_amazon_001"


def test_catalog_crud(repo):
    repo.upsert_store(TENANT_A, _store())
    repo.upsert_product(TENANT_A, _product())
    repo.upsert_sku(TENANT_A, _sku())
    assert repo.get_product(TENANT_A, "product_000021").title == "Mouse"
    assert repo.get_sku(TENANT_A, "sku_000087").merchant_sku == "merch-sku_000087"
    assert [s.sku_id for s in repo.list_skus_by_product(TENANT_A, "product_000021")] == ["sku_000087"]


def test_listing_and_listing_item(repo):
    repo.upsert_store(TENANT_A, _store())
    repo.upsert_product(TENANT_A, _product())
    repo.upsert_sku(TENANT_A, _sku())
    listing = Listing(
        listing_id="listing_000823", tenant_id=TENANT_A, store_id="store_amazon_001",
        platform="amazon", external_listing_id="B0ABC",
    )
    repo.upsert_listing(TENANT_A, listing)
    item = ListingItem(
        listing_item_id="listing_item_001029", listing_id="listing_000823",
        sku_id="sku_000087", external_sku_id="EXT-087", price=29.9,
    )
    repo.upsert_listing_item(TENANT_A, item)
    assert repo.get_listing(TENANT_A, "listing_000823").external_listing_id == "B0ABC"
    assert [i.listing_item_id for i in repo.list_listing_items_by_listing(TENANT_A, "listing_000823")] == ["listing_item_001029"]


def test_advertising_hierarchy(repo):
    repo.upsert_store(TENANT_A, _store())
    campaign = Campaign(
        campaign_id="campaign_000021", tenant_id=TENANT_A, store_id="store_amazon_001",
        platform="amazon", external_campaign_id="C1", name="SP",
    )
    repo.upsert_campaign(TENANT_A, campaign)
    group = AdGroup(ad_group_id="ag1", campaign_id="campaign_000021",
                    external_ad_group_id="AG1", name="g")
    repo.upsert_ad_group(TENANT_A, group)
    ad = Ad(ad_id="ad1", ad_group_id="ag1", external_ad_id="A1")
    repo.upsert_ad(TENANT_A, ad)
    repo.upsert_keyword(TENANT_A, Keyword(keyword_id="kw1", ad_group_id="ag1",
                                           external_keyword_id="K1", keyword_text="mouse"))
    repo.upsert_search_term(TENANT_A, SearchTerm(search_term_id="st1", ad_group_id="ag1",
                                                 search_term="mous"))
    assert len(repo.list_campaigns_by_store(TENANT_A, "store_amazon_001")) == 1
    assert len(repo.list_ad_groups_by_campaign(TENANT_A, "campaign_000021")) == 1
    assert len(repo.list_ads_by_ad_group(TENANT_A, "ag1")) == 1
    assert len(repo.list_keywords_by_ad_group(TENANT_A, "ag1")) == 1
    assert len(repo.list_search_terms_by_ad_group(TENANT_A, "ag1")) == 1


def test_review_and_insight(repo):
    repo.upsert_store(TENANT_A, _store())
    listing = Listing(listing_id="l1", tenant_id=TENANT_A, store_id="store_amazon_001",
                      platform="amazon", external_listing_id="B1")
    repo.upsert_listing(TENANT_A, listing)
    review = Review(review_id="r1", tenant_id=TENANT_A, store_id="store_amazon_001",
                    listing_id="l1", platform="amazon", external_review_id="R1", rating=4.0)
    repo.upsert_review(TENANT_A, review)
    insight = ReviewInsight(review_insight_id="ri1", review_id="r1", sentiment="positive")
    repo.upsert_review_insight(TENANT_A, insight)
    assert len(repo.list_reviews_by_listing(TENANT_A, "l1")) == 1
    assert len(repo.list_review_insights_by_review(TENANT_A, "r1")) == 1


# ── Tenant isolation ─────────────────────────────────────────

def test_cross_tenant_read_is_hidden(repo):
    repo.upsert_store(TENANT_A, _store())
    assert repo.get_store(TENANT_B, "store_amazon_001") is None
    assert repo.list_stores(TENANT_B) == []


def test_cross_tenant_write_is_rejected(repo):
    store = _store(tenant=TENANT_A)
    with pytest.raises(TenantIsolationViolation):
        repo.upsert_store(TENANT_B, store)


def test_cross_tenant_parent_reference_rejected(repo):
    repo.upsert_store(TENANT_A, _store())
    repo.upsert_product(TENANT_A, _product())
    sku_b = SKU(sku_id="sku_b", tenant_id=TENANT_B, product_id="product_000021",
                merchant_sku="m")
    with pytest.raises(TenantIsolationViolation):
        repo.upsert_sku(TENANT_B, sku_b)


def test_missing_parent_rejected(repo):
    with pytest.raises(CommerceStorageError):
        repo.upsert_sku(TENANT_A, _sku())


# ── Metric natural-key idempotency ───────────────────────────

def _metric(metric_record_id="mr1", value=100.0, period_start="2026-08-01",
            period_end="2026-08-02"):
    return MetricSeries(
        metric_record_id=metric_record_id, tenant_id=TENANT_A, subject_type="STORE",
        subject_id="store_amazon_001", metric_name="GMV", metric_class="AGGREGATED",
        granularity="DAILY", period_start=period_start, period_end=period_end,
        value=value, unit="USD",
    )


def test_metric_natural_key_idempotent(repo):
    first = repo.upsert_metric(TENANT_A, _metric("mr1", 100.0))
    second = repo.upsert_metric(TENANT_A, _metric("mr2", 150.0))
    assert first.metric_record_id == "mr1"
    assert second.metric_record_id == "mr1"  # stable id, no duplicate
    assert second.value == 150.0  # historical correction updates value
    rows = repo.query_metrics(TENANT_A, "STORE", "store_amazon_001", ["GMV"], "DAILY")
    assert len(rows) == 1


def test_metric_distinct_periods_coexist(repo):
    repo.upsert_metric(TENANT_A, _metric("mr1", 100.0, "2026-08-01", "2026-08-02"))
    repo.upsert_metric(TENANT_A, _metric("mr2", 200.0, "2026-08-02", "2026-08-03"))
    rows = repo.query_metrics(TENANT_A, "STORE", "store_amazon_001", ["GMV"], "DAILY")
    assert len(rows) == 2


# ── Inventory append-only ────────────────────────────────────

def _snapshot(snapshot_id="inv1", available=10, snapshot_at="2026-08-01T00:00:00+00:00",
              source="amazon"):
    return InventorySnapshot(
        inventory_snapshot_id=snapshot_id, tenant_id=TENANT_A,
        store_id="store_amazon_001", sku_id="sku_000087",
        available_quantity=available, snapshot_at=snapshot_at,
        source_metadata={"source": source},
    )


def test_inventory_append_semantics(repo):
    repo.upsert_store(TENANT_A, _store())
    repo.upsert_product(TENANT_A, _product())
    repo.upsert_sku(TENANT_A, _sku())
    assert repo.append_inventory_snapshot(TENANT_A, _snapshot("inv1", 10, "2026-08-01T00:00:00+00:00")) is True
    assert repo.append_inventory_snapshot(TENANT_A, _snapshot("inv1", 10, "2026-08-01T00:00:00+00:00")) is False
    assert repo.append_inventory_snapshot(TENANT_A, _snapshot("inv2", 5, "2026-08-02T00:00:00+00:00")) is True
    history = repo.list_inventory_history(TENANT_A, "store_amazon_001", "sku_000087")
    assert [s.inventory_snapshot_id for s in history] == ["inv1", "inv2"]
    latest = repo.get_latest_inventory(TENANT_A, "store_amazon_001", "sku_000087")
    assert latest.available_quantity == 5


# ── External identity map ────────────────────────────────────

def test_external_identity_stable(identity_map):
    ext = ExternalIdentity(
        tenant_id=TENANT_A, platform="amazon", store_id="store_amazon_001",
        resource_type="PRODUCT", external_id="ASIN1", canonical_id="product_000021",
    )
    assert identity_map.register(TENANT_A, ext) == "product_000021"
    # same external key + same canonical id -> idempotent success
    same = ExternalIdentity(
        tenant_id=TENANT_A, platform="amazon", store_id="store_amazon_001",
        resource_type="PRODUCT", external_id="ASIN1", canonical_id="product_000021",
    )
    assert identity_map.register(TENANT_A, same) == "product_000021"
    assert identity_map.resolve(TENANT_A, "amazon", "store_amazon_001", "PRODUCT", "ASIN1") == "product_000021"


def test_external_identity_conflict_fails_closed(identity_map):
    identity_map.register(TENANT_A, ExternalIdentity(
        tenant_id=TENANT_A, platform="amazon", store_id="store_amazon_001",
        resource_type="PRODUCT", external_id="ASIN1", canonical_id="product_000021",
    ))
    conflict = ExternalIdentity(
        tenant_id=TENANT_A, platform="amazon", store_id="store_amazon_001",
        resource_type="PRODUCT", external_id="ASIN1", canonical_id="product_999",
    )
    with pytest.raises(ExternalIdentityConflict):
        identity_map.register(TENANT_A, conflict)
    # original mapping unchanged
    assert identity_map.resolve(TENANT_A, "amazon", "store_amazon_001", "PRODUCT", "ASIN1") == "product_000021"


def test_external_identity_tenant_scoped(identity_map):
    identity_map.register(TENANT_A, ExternalIdentity(
        tenant_id=TENANT_A, platform="amazon", store_id="s", resource_type="PRODUCT",
        external_id="ASIN1", canonical_id="p1",
    ))
    assert identity_map.resolve(TENANT_B, "amazon", "s", "PRODUCT", "ASIN1") is None
