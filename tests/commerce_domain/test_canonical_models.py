"""Canonical Commerce Model tests: serialization round-trips and relationship
invariants.  No platform-specific field may leak into the canonical core."""

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
    Order,
    OrderItem,
    Product,
    Review,
    ReviewInsight,
    SKU,
    SearchTerm,
    Store,
    MetricDefinition,
    MetricSeries,
    OperationalIssue,
)


def _roundtrip(entity):
    return entity.__class__.from_dict(entity.to_dict())


def test_store_roundtrip():
    store = Store(
        store_id="store_amazon_001", tenant_id="company_A", platform="amazon",
        marketplace="US", external_store_id="A1B2C3", name="Amazon001",
        currency="USD", timezone="America/New_York",
    )
    assert _roundtrip(store) == store


def test_product_roundtrip():
    product = Product(
        product_id="product_000021", tenant_id="company_A", title="Wireless Mouse",
        brand="Acme", category="Electronics", attributes={"color": "black"},
    )
    assert _roundtrip(product) == product


def test_sku_roundtrip():
    sku = SKU(
        sku_id="sku_000087", tenant_id="company_A", product_id="product_000021",
        merchant_sku="SKU-087", variant_attributes={"color": "black"}, cost=12.5,
    )
    assert _roundtrip(sku) == sku


def test_listing_has_no_sku_id():
    listing = Listing(
        listing_id="listing_000823", tenant_id="company_A", store_id="store_amazon_001",
        platform="amazon", external_listing_id="B0ABC",
    )
    assert not hasattr(listing, "sku_id")
    assert _roundtrip(listing) == listing


def test_listing_item_links_listing_and_sku():
    item = ListingItem(
        listing_item_id="listing_item_001029", listing_id="listing_000823",
        sku_id="sku_000087", external_sku_id="EXT-087", price=29.9,
    )
    assert item.listing_id == "listing_000823"
    assert item.sku_id == "sku_000087"
    assert _roundtrip(item) == item


def test_order_and_order_item_roundtrip():
    order = Order(
        order_id="order_000001", tenant_id="company_A", store_id="store_amazon_001",
        external_order_id="EXT-ORD-1", status="shipped", gross_amount=100.0,
        net_amount=90.0,
    )
    item = OrderItem(
        order_item_id="order_item_000001", order_id="order_000001",
        sku_id="sku_000087", quantity=2, unit_price=45.0, net_amount=90.0,
    )
    assert _roundtrip(order) == order
    assert _roundtrip(item) == item


def test_inventory_snapshot_roundtrip():
    snap = InventorySnapshot(
        inventory_snapshot_id="inv_000001", tenant_id="company_A",
        store_id="store_amazon_001", sku_id="sku_000087",
        on_hand_quantity=100, available_quantity=80,
    )
    assert _roundtrip(snap) == snap


def test_advertising_hierarchy_roundtrip():
    campaign = Campaign(
        campaign_id="campaign_000021", tenant_id="company_A",
        store_id="store_amazon_001", platform="amazon",
        external_campaign_id="CAMP-1", name="SP Main",
        campaign_type="PRODUCT", objective="SALES",
    )
    group = AdGroup(
        ad_group_id="ad_group_000001", campaign_id="campaign_000021",
        external_ad_group_id="AG-1", name="Main Group", targeting_type="KEYWORD",
    )
    ad = Ad(ad_id="ad_000001", ad_group_id="ad_group_000001", external_ad_id="AD-1")
    promoted = AdPromotedItem(
        ad_promoted_item_id="api_000001", ad_id="ad_000001",
        listing_id="listing_000823",
    )
    keyword = Keyword(
        keyword_id="keyword_000001", ad_group_id="ad_group_000001",
        external_keyword_id="KW-1", keyword_text="wireless mouse", match_type="EXACT",
    )
    term = SearchTerm(
        search_term_id="search_term_000001", ad_group_id="ad_group_000001",
        search_term="wirless mouse",
    )
    for entity in (campaign, group, ad, promoted, keyword, term):
        assert _roundtrip(entity) == entity


def test_ad_has_no_direct_sku_or_listing():
    ad = Ad(ad_id="ad_000001", ad_group_id="ad_group_000001", external_ad_id="AD-1")
    assert not hasattr(ad, "sku_id")
    assert not hasattr(ad, "listing_id")


def test_review_has_single_derivable_location():
    review = Review(
        review_id="review_000001", tenant_id="company_A", store_id="store_amazon_001",
        listing_id="listing_000823", platform="amazon",
        external_review_id="R-1", rating=4.0,
    )
    assert not hasattr(review, "product_id")
    assert not hasattr(review, "sku_id")
    assert _roundtrip(review) == review


def test_review_insight_roundtrip():
    insight = ReviewInsight(
        review_insight_id="ri_000001", review_id="review_000001",
        sentiment="negative", topics=("durability",), confidence=0.9,
        model_provider="openai", model_version="gpt-4o", extractor_version="1.0",
    )
    assert _roundtrip(insight) == insight


def test_metric_series_and_definition_roundtrip():
    series = MetricSeries(
        metric_record_id="mr_000001", tenant_id="company_A", subject_type="STORE",
        subject_id="store_amazon_001", metric_name="GMV", metric_class="AGGREGATED",
        granularity="DAILY", period_start="2026-08-01", period_end="2026-08-02",
        value=1000.0, unit="USD",
    )
    definition = MetricDefinition(
        metric="ROAS", metric_class="DERIVED", version="1.0",
        dependencies=("AD_SALES", "AD_SPEND"), formula="AD_SALES / AD_SPEND",
        zero_policy="NULL",
    )
    assert _roundtrip(series) == series
    assert _roundtrip(definition) == definition
    assert definition.dependencies == ("AD_SALES", "AD_SPEND")


def test_operational_issue_roundtrip():
    issue = OperationalIssue(
        issue_id="issue_000001", tenant_id="company_A", store_id="store_amazon_001",
        domain="sales", subject_type="STORE", subject_id="store_amazon_001",
        issue_type="GMV_DECLINE", severity="high", priority="P1",
        recommendation_codes=("REVIEW_PRICE_CHANGE",),
    )
    assert _roundtrip(issue) == issue


def test_external_identity_roundtrip():
    ext = ExternalIdentity(
        tenant_id="company_A", platform="amazon", store_id="store_amazon_001",
        resource_type="PRODUCT", external_id="ASIN123", canonical_id="product_000021",
    )
    assert _roundtrip(ext) == ext
