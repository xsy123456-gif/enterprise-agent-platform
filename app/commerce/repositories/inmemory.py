"""In-memory implementation of the canonical commerce store.

Used for unit tests and the development composition.  Mirrors the PostgreSQL
implementation exactly: tenant isolation, parent-tenant verification, metric
natural-key idempotency and append-only inventory.
"""

from app.commerce.contracts.errors import CommerceValidationError
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
from app.commerce.domain.metrics import canonical_dimensions_hash
from app.commerce.repositories.errors import (
    CommerceStorageError,
    ExternalIdentityConflict,
    TenantIsolationViolation,
)
from app.commerce.repositories.ports import CommerceRepository, ExternalIdentityMap


def _metric_dimensions_hash(series):
    computed = canonical_dimensions_hash(series.dimensions)
    if series.dimensions_hash and series.dimensions_hash != computed:
        raise CommerceValidationError(
            f"dimensions_hash {series.dimensions_hash!r} does not match canonical "
            f"hash {computed!r} for dimensions {series.dimensions!r}"
        )
    return computed


class InMemoryCommerceRepository(CommerceRepository):

    def __init__(self):
        self._stores = {}
        self._products = {}
        self._skus = {}
        self._listings = {}
        self._listing_items = {}
        self._campaigns = {}
        self._ad_groups = {}
        self._ads = {}
        self._ad_promoted_items = {}
        self._keywords = {}
        self._search_terms = {}
        self._reviews = {}
        self._review_insights = {}
        self._review_insight_natural = {}
        self._inventory = []
        self._inventory_keys = set()
        self._metrics = {}
        self._initialized = False

    # ── Schema / lifecycle (no-op for in-memory) ──────────────

    def initialize(self):
        self._initialized = True

    def validate_schema(self):
        return {"tables": "in-memory"}

    def healthcheck(self):
        self._initialized = True

    # ── Store ─────────────────────────────────────────────────

    def upsert_store(self, tenant_id, store):
        self._require_tenant(tenant_id, store.tenant_id)
        self._stores[store.store_id] = store
        return store

    def get_store(self, tenant_id, store_id):
        store = self._stores.get(store_id)
        return store if store and store.tenant_id == tenant_id else None

    def list_stores(self, tenant_id):
        return sorted(
            (s for s in self._stores.values() if s.tenant_id == tenant_id),
            key=lambda s: s.store_id,
        )

    def find_store_by_external(self, tenant_id, platform, external_store_id):
        for store in self._stores.values():
            if (store.tenant_id == tenant_id and store.platform == platform
                    and store.external_store_id == external_store_id):
                return store
        return None

    def resolve_store_id_by_external(self, tenant_id, platform, external_store_id):
        for store in self._stores.values():
            if (store.tenant_id == tenant_id and store.platform == platform
                    and store.external_store_id == external_store_id):
                return store.store_id
        return None

    # ── Catalog ───────────────────────────────────────────────

    def upsert_product(self, tenant_id, product):
        self._require_tenant(tenant_id, product.tenant_id)
        self._products[product.product_id] = product
        return product

    def get_product(self, tenant_id, product_id):
        product = self._products.get(product_id)
        return product if product and product.tenant_id == tenant_id else None

    def list_products(self, tenant_id):
        return sorted(
            (p for p in self._products.values() if p.tenant_id == tenant_id),
            key=lambda p: p.product_id,
        )

    def upsert_sku(self, tenant_id, sku):
        self._require_tenant(tenant_id, sku.tenant_id)
        self._verify_parent(tenant_id, self._products, sku.product_id)
        self._skus[sku.sku_id] = sku
        return sku

    def get_sku(self, tenant_id, sku_id):
        sku = self._skus.get(sku_id)
        return sku if sku and sku.tenant_id == tenant_id else None

    def list_skus_by_product(self, tenant_id, product_id):
        return sorted(
            (s for s in self._skus.values()
             if s.tenant_id == tenant_id and s.product_id == product_id),
            key=lambda s: s.sku_id,
        )

    def upsert_listing(self, tenant_id, listing):
        self._require_tenant(tenant_id, listing.tenant_id)
        self._verify_parent(tenant_id, self._stores, listing.store_id)
        self._listings[listing.listing_id] = listing
        return listing

    def get_listing(self, tenant_id, listing_id):
        listing = self._listings.get(listing_id)
        return listing if listing and listing.tenant_id == tenant_id else None

    def list_listings_by_store(self, tenant_id, store_id):
        return sorted(
            (l for l in self._listings.values()
             if l.tenant_id == tenant_id and l.store_id == store_id),
            key=lambda l: l.listing_id,
        )

    def upsert_listing_item(self, tenant_id, item):
        self._verify_parent(tenant_id, self._listings, item.listing_id)
        self._verify_parent(tenant_id, self._skus, item.sku_id)
        self._listing_items[item.listing_item_id] = (tenant_id, item)
        return item

    def get_listing_item(self, tenant_id, listing_item_id):
        entry = self._listing_items.get(listing_item_id)
        return entry[1] if entry and entry[0] == tenant_id else None

    def list_listing_items_by_listing(self, tenant_id, listing_id):
        return sorted(
            (i for t, i in self._listing_items.values()
             if t == tenant_id and i.listing_id == listing_id),
            key=lambda i: i.listing_item_id,
        )

    # ── Inventory (append-only) ───────────────────────────────

    def append_inventory_snapshot(self, tenant_id, snapshot):
        self._require_tenant(tenant_id, snapshot.tenant_id)
        self._verify_parent(tenant_id, self._stores, snapshot.store_id)
        self._verify_parent(tenant_id, self._skus, snapshot.sku_id)
        source = (snapshot.source_metadata or {}).get("source", "default")
        key = (snapshot.tenant_id, snapshot.store_id, snapshot.sku_id,
               snapshot.snapshot_at, source)
        if key in self._inventory_keys:
            return False
        self._inventory_keys.add(key)
        self._inventory.append(snapshot)
        return True

    def get_latest_inventory(self, tenant_id, store_id, sku_id):
        candidates = sorted(
            (s for s in self._inventory
             if s.tenant_id == tenant_id and s.store_id == store_id and s.sku_id == sku_id),
            key=lambda s: (s.snapshot_at, s.inventory_snapshot_id),
        )
        return candidates[-1] if candidates else None

    def list_inventory_history(self, tenant_id, store_id, sku_id):
        return sorted(
            (s for s in self._inventory
             if s.tenant_id == tenant_id and s.store_id == store_id and s.sku_id == sku_id),
            key=lambda s: s.snapshot_at,
        )

    # ── Advertising ───────────────────────────────────────────

    def upsert_campaign(self, tenant_id, campaign):
        self._require_tenant(tenant_id, campaign.tenant_id)
        self._verify_parent(tenant_id, self._stores, campaign.store_id)
        self._campaigns[campaign.campaign_id] = campaign
        return campaign

    def get_campaign(self, tenant_id, campaign_id):
        campaign = self._campaigns.get(campaign_id)
        return campaign if campaign and campaign.tenant_id == tenant_id else None

    def list_campaigns_by_store(self, tenant_id, store_id):
        return sorted(
            (c for c in self._campaigns.values()
             if c.tenant_id == tenant_id and c.store_id == store_id),
            key=lambda c: c.campaign_id,
        )

    def upsert_ad_group(self, tenant_id, ad_group):
        self._verify_parent(tenant_id, self._campaigns, ad_group.campaign_id)
        self._ad_groups[ad_group.ad_group_id] = (tenant_id, ad_group)
        return ad_group

    def list_ad_groups_by_campaign(self, tenant_id, campaign_id):
        return sorted(
            (g for t, g in self._ad_groups.values()
             if t == tenant_id and g.campaign_id == campaign_id),
            key=lambda g: g.ad_group_id,
        )

    def upsert_ad(self, tenant_id, ad):
        self._verify_parent(tenant_id, self._ad_groups, ad.ad_group_id)
        self._ads[ad.ad_id] = (tenant_id, ad)
        return ad

    def list_ads_by_ad_group(self, tenant_id, ad_group_id):
        return sorted(
            (a for t, a in self._ads.values()
             if t == tenant_id and a.ad_group_id == ad_group_id),
            key=lambda a: a.ad_id,
        )

    def upsert_ad_promoted_item(self, tenant_id, item):
        self._verify_parent(tenant_id, self._ads, item.ad_id)
        self._verify_parent(tenant_id, self._listings, item.listing_id)
        self._ad_promoted_items[item.ad_promoted_item_id] = (tenant_id, item)
        return item

    def list_promoted_items_by_ad(self, tenant_id, ad_id):
        return sorted(
            (i for t, i in self._ad_promoted_items.values()
             if t == tenant_id and i.ad_id == ad_id),
            key=lambda i: i.ad_promoted_item_id,
        )

    def upsert_keyword(self, tenant_id, keyword):
        self._verify_parent(tenant_id, self._ad_groups, keyword.ad_group_id)
        self._keywords[keyword.keyword_id] = (tenant_id, keyword)
        return keyword

    def list_keywords_by_ad_group(self, tenant_id, ad_group_id):
        return sorted(
            (k for t, k in self._keywords.values()
             if t == tenant_id and k.ad_group_id == ad_group_id),
            key=lambda k: k.keyword_id,
        )

    def upsert_search_term(self, tenant_id, term):
        self._verify_parent(tenant_id, self._ad_groups, term.ad_group_id)
        self._search_terms[term.search_term_id] = (tenant_id, term)
        return term

    def list_search_terms_by_ad_group(self, tenant_id, ad_group_id):
        return sorted(
            (s for t, s in self._search_terms.values()
             if t == tenant_id and s.ad_group_id == ad_group_id),
            key=lambda s: s.search_term_id,
        )

    # ── Review / ReviewInsight ────────────────────────────────

    def upsert_review(self, tenant_id, review):
        self._require_tenant(tenant_id, review.tenant_id)
        self._verify_parent(tenant_id, self._stores, review.store_id)
        self._verify_parent(tenant_id, self._listings, review.listing_id)
        self._reviews[review.review_id] = review
        return review

    def get_review(self, tenant_id, review_id):
        review = self._reviews.get(review_id)
        return review if review and review.tenant_id == tenant_id else None

    def list_reviews_by_listing(self, tenant_id, listing_id):
        return sorted(
            (r for r in self._reviews.values()
             if r.tenant_id == tenant_id and r.listing_id == listing_id),
            key=lambda r: r.review_id,
        )

    def upsert_review_insight(self, tenant_id, insight):
        self._verify_parent(tenant_id, self._reviews, insight.review_id)
        key = (tenant_id, insight.review_id, insight.extractor_id,
               insight.extractor_version)
        existing_id = self._review_insight_natural.get(key)
        if existing_id is not None:
            return self._review_insights[existing_id][1]
        self._review_insight_natural[key] = insight.review_insight_id
        self._review_insights[insight.review_insight_id] = (tenant_id, insight)
        return insight

    def list_review_insights_by_review(self, tenant_id, review_id):
        return sorted(
            (i for t, i in self._review_insights.values()
             if t == tenant_id and i.review_id == review_id),
            key=lambda i: i.review_insight_id,
        )

    def get_review_insight(self, tenant_id, review_insight_id):
        entry = self._review_insights.get(review_insight_id)
        return entry[1] if entry and entry[0] == tenant_id else None

    def list_review_insights_by_listing(self, tenant_id, listing_id):
        review_ids = {
            r.review_id for r in self._reviews.values()
            if r.tenant_id == tenant_id and r.listing_id == listing_id
        }
        return sorted(
            (i for t, i in self._review_insights.values()
             if t == tenant_id and i.review_id in review_ids),
            key=lambda i: i.review_insight_id,
        )

    def exists_review_insight(self, tenant_id, review_id, extractor_id, extractor_version):
        return (tenant_id, review_id, extractor_id, extractor_version) in \
            self._review_insight_natural

    # ── Metric (natural-key idempotent) ───────────────────────

    def upsert_metric(self, tenant_id, series):
        self._require_tenant(tenant_id, series.tenant_id)
        dimensions_hash = _metric_dimensions_hash(series)
        normalized = MetricSeries(
            metric_record_id=series.metric_record_id, tenant_id=series.tenant_id,
            subject_type=series.subject_type, subject_id=series.subject_id,
            metric_name=series.metric_name, metric_class=series.metric_class,
            granularity=series.granularity, period_start=series.period_start,
            period_end=series.period_end, value=series.value, unit=series.unit,
            dimensions=dict(series.dimensions), dimensions_hash=dimensions_hash,
            source_metadata=dict(series.source_metadata), updated_at=series.updated_at,
        )
        key = self._metric_key(normalized)
        existing = self._metrics.get(key)
        if existing is not None:
            updated = MetricSeries(
                metric_record_id=existing.metric_record_id,
                tenant_id=existing.tenant_id,
                subject_type=existing.subject_type,
                subject_id=existing.subject_id,
                metric_name=existing.metric_name,
                metric_class=normalized.metric_class,
                granularity=existing.granularity,
                period_start=existing.period_start,
                period_end=existing.period_end,
                value=normalized.value,
                unit=normalized.unit,
                dimensions=dict(normalized.dimensions),
                dimensions_hash=existing.dimensions_hash,
                source_metadata=dict(normalized.source_metadata),
                updated_at=normalized.updated_at,
            )
            self._metrics[key] = updated
            return updated
        self._metrics[key] = normalized
        return normalized

    def query_metrics(self, tenant_id, subject_type, subject_id,
                      metric_names=None, granularity=None,
                      period_start=None, period_end=None):
        results = []
        for series in self._metrics.values():
            if series.tenant_id != tenant_id:
                continue
            if series.subject_type != subject_type or series.subject_id != subject_id:
                continue
            if metric_names and series.metric_name not in metric_names:
                continue
            if granularity and series.granularity != granularity:
                continue
            if period_start and series.period_end <= period_start:
                continue
            if period_end and series.period_start > period_end:
                continue
            results.append(series)
        return sorted(results, key=lambda s: (s.period_start, s.metric_name))

    # ── Internal helpers ──────────────────────────────────────

    @staticmethod
    def _metric_key(series):
        return (series.tenant_id, series.subject_type, series.subject_id,
                series.metric_name, series.period_start, series.period_end,
                series.granularity, series.dimensions_hash)

    @staticmethod
    def _require_tenant(tenant_id, entity_tenant_id):
        if entity_tenant_id is not None and entity_tenant_id != tenant_id:
            raise TenantIsolationViolation(
                f"cross-tenant write denied: expected {tenant_id!r}, "
                f"got {entity_tenant_id!r}"
            )

    def _verify_parent(self, tenant_id, table, parent_id):
        if parent_id is None:
            raise CommerceStorageError("parent reference is required")
        value = table.get(parent_id)
        if value is None:
            raise CommerceStorageError(f"parent not found: {parent_id!r}")
        if isinstance(value, tuple):
            owner = value[0]
        else:
            owner = value.tenant_id
        if owner != tenant_id:
            raise TenantIsolationViolation(
                f"cross-tenant parent reference: {parent_id!r}"
            )


class InMemoryExternalIdentityMap(ExternalIdentityMap):

    def __init__(self):
        self._identities = {}

    def resolve(self, tenant_id, platform, store_id, resource_type, external_id):
        identity = self._identities.get(
            (tenant_id, platform, store_id, resource_type, external_id)
        )
        return identity.canonical_id if identity else None

    def register(self, tenant_id, identity):
        key = (identity.tenant_id, identity.platform, identity.store_id,
               identity.resource_type, identity.external_id)
        existing = self._identities.get(key)
        if existing is None:
            self._identities[key] = identity
            return identity.canonical_id
        if existing.canonical_id != identity.canonical_id:
            raise ExternalIdentityConflict(
                f"external identity conflict for "
                f"{identity.resource_type}:{identity.external_id}: "
                f"canonical_id {existing.canonical_id!r} already mapped, "
                f"cannot remap to {identity.canonical_id!r}"
            )
        return existing.canonical_id

    def list(self, tenant_id):
        return sorted(
            (i for k, i in self._identities.items() if k[0] == tenant_id),
            key=lambda i: (i.resource_type, i.external_id),
        )


__all__ = ["InMemoryCommerceRepository", "InMemoryExternalIdentityMap"]
