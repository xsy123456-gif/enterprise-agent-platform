"""Commerce repository ports.

The abstract boundary for canonical commerce persistence.  Two ports:

- ``CommerceRepository`` — entity CRUD/query, Metric natural-key upsert,
  InventorySnapshot append-only semantics.
- ``ExternalIdentityMap`` — stable external-id -> canonical-id resolution.

Every method takes ``tenant_id`` as an explicit first argument; implementations
must enforce tenant isolation (never read tenant from an entity the caller
supplies) and must fail closed on cross-tenant references.
"""

from abc import ABC, abstractmethod

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


class CommerceRepository(ABC):
    """Canonical commerce store."""

    # ── Store ──────────────────────────────────────────────
    @abstractmethod
    def upsert_store(self, tenant_id: str, store: Store) -> Store:
        pass

    @abstractmethod
    def get_store(self, tenant_id: str, store_id: str) -> Store | None:
        pass

    @abstractmethod
    def list_stores(self, tenant_id: str) -> list[Store]:
        pass

    @abstractmethod
    def find_store_by_external(
        self, tenant_id: str, platform: str, external_store_id: str,
    ) -> Store | None:
        pass

    @abstractmethod
    def resolve_store_id_by_external(
        self, tenant_id: str, platform: str, external_store_id: str,
    ) -> str | None:
        pass

    # ── Catalog: Product / SKU / Listing / ListingItem ─────
    @abstractmethod
    def upsert_product(self, tenant_id: str, product: Product) -> Product:
        pass

    @abstractmethod
    def get_product(self, tenant_id: str, product_id: str) -> Product | None:
        pass

    @abstractmethod
    def list_products(self, tenant_id: str) -> list[Product]:
        pass

    @abstractmethod
    def upsert_sku(self, tenant_id: str, sku: SKU) -> SKU:
        pass

    @abstractmethod
    def get_sku(self, tenant_id: str, sku_id: str) -> SKU | None:
        pass

    @abstractmethod
    def list_skus_by_product(self, tenant_id: str, product_id: str) -> list[SKU]:
        pass

    @abstractmethod
    def upsert_listing(self, tenant_id: str, listing: Listing) -> Listing:
        pass

    @abstractmethod
    def get_listing(self, tenant_id: str, listing_id: str) -> Listing | None:
        pass

    @abstractmethod
    def list_listings_by_store(self, tenant_id: str, store_id: str) -> list[Listing]:
        pass

    @abstractmethod
    def upsert_listing_item(self, tenant_id: str, item: ListingItem) -> ListingItem:
        pass

    @abstractmethod
    def get_listing_item(self, tenant_id: str, listing_item_id: str) -> ListingItem | None:
        pass

    @abstractmethod
    def list_listing_items_by_listing(self, tenant_id: str, listing_id: str) -> list[ListingItem]:
        pass

    # ── Inventory (append-only) ────────────────────────────
    @abstractmethod
    def append_inventory_snapshot(self, tenant_id: str, snapshot: InventorySnapshot) -> bool:
        pass

    @abstractmethod
    def get_latest_inventory(self, tenant_id: str, store_id: str, sku_id: str) -> InventorySnapshot | None:
        pass

    @abstractmethod
    def list_inventory_history(self, tenant_id: str, store_id: str, sku_id: str) -> list[InventorySnapshot]:
        pass

    # ── Advertising ────────────────────────────────────────
    @abstractmethod
    def upsert_campaign(self, tenant_id: str, campaign: Campaign) -> Campaign:
        pass

    @abstractmethod
    def get_campaign(self, tenant_id: str, campaign_id: str) -> Campaign | None:
        pass

    @abstractmethod
    def list_campaigns_by_store(self, tenant_id: str, store_id: str) -> list[Campaign]:
        pass

    @abstractmethod
    def upsert_ad_group(self, tenant_id: str, ad_group: AdGroup) -> AdGroup:
        pass

    @abstractmethod
    def list_ad_groups_by_campaign(self, tenant_id: str, campaign_id: str) -> list[AdGroup]:
        pass

    @abstractmethod
    def upsert_ad(self, tenant_id: str, ad: Ad) -> Ad:
        pass

    @abstractmethod
    def list_ads_by_ad_group(self, tenant_id: str, ad_group_id: str) -> list[Ad]:
        pass

    @abstractmethod
    def upsert_ad_promoted_item(self, tenant_id: str, item: AdPromotedItem) -> AdPromotedItem:
        pass

    @abstractmethod
    def list_promoted_items_by_ad(self, tenant_id: str, ad_id: str) -> list[AdPromotedItem]:
        pass

    @abstractmethod
    def upsert_keyword(self, tenant_id: str, keyword: Keyword) -> Keyword:
        pass

    @abstractmethod
    def list_keywords_by_ad_group(self, tenant_id: str, ad_group_id: str) -> list[Keyword]:
        pass

    @abstractmethod
    def upsert_search_term(self, tenant_id: str, term: SearchTerm) -> SearchTerm:
        pass

    @abstractmethod
    def list_search_terms_by_ad_group(self, tenant_id: str, ad_group_id: str) -> list[SearchTerm]:
        pass

    # ── Review / ReviewInsight ─────────────────────────────
    @abstractmethod
    def upsert_review(self, tenant_id: str, review: Review) -> Review:
        pass

    @abstractmethod
    def get_review(self, tenant_id: str, review_id: str) -> Review | None:
        pass

    @abstractmethod
    def list_reviews_by_listing(self, tenant_id: str, listing_id: str) -> list[Review]:
        pass

    @abstractmethod
    def upsert_review_insight(self, tenant_id: str, insight: ReviewInsight) -> ReviewInsight:
        pass

    @abstractmethod
    def list_review_insights_by_review(self, tenant_id: str, review_id: str) -> list[ReviewInsight]:
        pass

    # ── Metric (natural-key idempotent) ────────────────────
    @abstractmethod
    def upsert_metric(self, tenant_id: str, series: MetricSeries) -> MetricSeries:
        pass

    @abstractmethod
    def query_metrics(
        self,
        tenant_id: str,
        subject_type: str,
        subject_id: str,
        metric_names: list[str] | None = None,
        granularity: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> list[MetricSeries]:
        pass

    # ── Schema / lifecycle ─────────────────────────────────
    @abstractmethod
    def initialize(self) -> None:
        pass

    @abstractmethod
    def validate_schema(self) -> dict:
        pass

    @abstractmethod
    def healthcheck(self) -> None:
        pass


class ExternalIdentityMap(ABC):
    """Stable external-id -> canonical-id mapping."""

    @abstractmethod
    def resolve(
        self, tenant_id: str, platform: str, store_id: str,
        resource_type: str, external_id: str,
    ) -> str | None:
        pass

    @abstractmethod
    def register(self, tenant_id: str, identity: ExternalIdentity) -> str:
        pass

    @abstractmethod
    def list(self, tenant_id: str) -> list[ExternalIdentity]:
        pass


__all__ = ["CommerceRepository", "ExternalIdentityMap"]
