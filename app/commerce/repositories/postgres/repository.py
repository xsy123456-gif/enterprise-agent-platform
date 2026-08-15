"""PostgreSQL implementation of the canonical commerce store.

Every write verifies tenant ownership (fail-closed): top-level entities must
carry the caller's ``tenant_id``, and nested entities verify their direct
parent belongs to the same tenant.  Metric records are idempotent on their
natural key; inventory snapshots are append-only on theirs.
"""

import json
from contextlib import contextmanager

from app.commerce.contracts.errors import CommerceValidationError
from app.commerce.domain import (
    Ad,
    AdGroup,
    AdPromotedItem,
    Campaign,
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
    TenantIsolationViolation,
)
from app.commerce.repositories.ports import CommerceRepository
from app.commerce.repositories.postgres.migrations import (
    apply_migrations,
    current_schema_version,
)
from app.commerce.repositories.postgres.schema import (
    REQUIRED_COLUMNS,
    TABLES,
    build_schema_sql,
)


def _json(value):
    return json.dumps(value, ensure_ascii=False)


def _to_tuple(value):
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return (value,)


def _inventory_source(snapshot):
    """Source identity for an inventory snapshot (part of its natural key).

    Distinct sources for the same (store, sku, snapshot_at) must not overwrite
    each other.
    """
    return (snapshot.source_metadata or {}).get("source", "default")


def _metric_dimensions_hash(series):
    """Canonical, deterministic dimensions hash for the metric natural key.

    A caller-supplied hash must equal the canonical hash, otherwise the write is
    rejected (fail-closed) so the natural key can never be non-deterministic.
    """
    computed = canonical_dimensions_hash(series.dimensions)
    if series.dimensions_hash and series.dimensions_hash != computed:
        raise CommerceValidationError(
            f"dimensions_hash {series.dimensions_hash!r} does not match canonical "
            f"hash {computed!r} for dimensions {series.dimensions!r}"
        )
    return computed


class PostgresCommerceRepository(CommerceRepository):

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    # ── Lifecycle / schema ────────────────────────────────────

    def initialize(self):
        """Development/test bootstrap: apply the idempotent DDL directly.

        Production must not use this for schema evolution; it should use
        ``migrate()`` so every schema change is versioned and recorded.
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(build_schema_sql())
        self.validate_schema()

    def migrate(self):
        """Apply pending versioned migrations (production schema evolution)."""
        with self._connection() as conn:
            apply_migrations(conn)
        self.validate_schema()

    def schema_version(self) -> int:
        with self._connection() as conn:
            return current_schema_version(conn)

    def healthcheck(self):
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT current_setting('server_version_num')::integer")
                version = cursor.fetchone()[0]
        if version < 160000:
            raise CommerceStorageError(
                "Commerce canonical store requires PostgreSQL 16 or newer"
            )

    def validate_schema(self) -> dict:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname=current_schema()"
                )
                tables = {row[0] for row in cursor.fetchall()}
                cursor.execute(
                    "SELECT table_name, column_name FROM information_schema.columns "
                    "WHERE table_schema = current_schema() AND table_name = ANY(%s)",
                    (list(TABLES),),
                )
                columns = {}
                for table, column in cursor.fetchall():
                    columns.setdefault(table, set()).add(column)
        missing = TABLES - tables
        if missing:
            raise CommerceStorageError(
                f"Commerce schema is missing tables: {sorted(missing)}"
            )
        missing_columns = {
            table: sorted(required - columns.get(table, set()))
            for table, required in REQUIRED_COLUMNS.items()
            if required - columns.get(table, set())
        }
        if missing_columns:
            raise CommerceStorageError(
                f"Commerce schema is missing required columns: {missing_columns}"
            )
        return {"tables": tables}

    # ── Store ─────────────────────────────────────────────────

    def upsert_store(self, tenant_id, store):
        self._require_tenant(tenant_id, store.tenant_id)
        with self._connection() as conn:
            self._execute(
                conn,
                """INSERT INTO commerce_stores
                (store_id, tenant_id, platform, marketplace, external_store_id, name,
                 currency, timezone, status, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (store_id) DO UPDATE SET
                 platform=EXCLUDED.platform, marketplace=EXCLUDED.marketplace,
                 external_store_id=EXCLUDED.external_store_id, name=EXCLUDED.name,
                 currency=EXCLUDED.currency, timezone=EXCLUDED.timezone,
                 status=EXCLUDED.status, updated_at=EXCLUDED.updated_at""",
                (store.store_id, store.tenant_id, store.platform, store.marketplace,
                 store.external_store_id, store.name, store.currency, store.timezone,
                 store.status, store.created_at, store.updated_at),
            )
        return store

    def get_store(self, tenant_id, store_id):
        row = self._fetch_row(
            "SELECT * FROM commerce_stores WHERE tenant_id=%s AND store_id=%s",
            (tenant_id, store_id),
        )
        return Store.from_dict(row) if row else None

    def list_stores(self, tenant_id):
        rows = self._fetch_rows(
            "SELECT * FROM commerce_stores WHERE tenant_id=%s ORDER BY store_id",
            (tenant_id,),
        )
        return [Store.from_dict(row) for row in rows]

    def find_store_by_external(self, tenant_id, platform, external_store_id):
        row = self._fetch_row(
            "SELECT * FROM commerce_stores WHERE tenant_id=%s AND platform=%s "
            "AND external_store_id=%s",
            (tenant_id, platform, external_store_id),
        )
        return Store.from_dict(row) if row else None

    def resolve_store_id_by_external(self, tenant_id, platform, external_store_id):
        row = self._fetch_row(
            "SELECT store_id FROM commerce_stores WHERE tenant_id=%s AND platform=%s "
            "AND external_store_id=%s",
            (tenant_id, platform, external_store_id),
        )
        return row["store_id"] if row else None

    # ── Catalog ───────────────────────────────────────────────

    def upsert_product(self, tenant_id, product):
        self._require_tenant(tenant_id, product.tenant_id)
        with self._connection() as conn:
            self._execute(
                conn,
                """INSERT INTO commerce_products
                (product_id, tenant_id, title, brand, category, product_type,
                 attributes, status, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                ON CONFLICT (product_id) DO UPDATE SET
                 title=EXCLUDED.title, brand=EXCLUDED.brand, category=EXCLUDED.category,
                 product_type=EXCLUDED.product_type, attributes=EXCLUDED.attributes,
                 status=EXCLUDED.status, updated_at=EXCLUDED.updated_at""",
                (product.product_id, product.tenant_id, product.title, product.brand,
                 product.category, product.product_type, _json(product.attributes),
                 product.status, product.created_at, product.updated_at),
            )
        return product

    def get_product(self, tenant_id, product_id):
        row = self._fetch_row(
            "SELECT * FROM commerce_products WHERE tenant_id=%s AND product_id=%s",
            (tenant_id, product_id),
        )
        return Product.from_dict(row) if row else None

    def list_products(self, tenant_id):
        rows = self._fetch_rows(
            "SELECT * FROM commerce_products WHERE tenant_id=%s ORDER BY product_id",
            (tenant_id,),
        )
        return [Product.from_dict(row) for row in rows]

    def upsert_sku(self, tenant_id, sku):
        self._require_tenant(tenant_id, sku.tenant_id)
        self._verify_parent_tenant(tenant_id, "commerce_products", "product_id", sku.product_id)
        with self._connection() as conn:
            self._execute(
                conn,
                """INSERT INTO commerce_skus
                (sku_id, tenant_id, product_id, merchant_sku, variant_attributes,
                 cost, status, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
                ON CONFLICT (sku_id) DO UPDATE SET
                 product_id=EXCLUDED.product_id, merchant_sku=EXCLUDED.merchant_sku,
                 variant_attributes=EXCLUDED.variant_attributes, cost=EXCLUDED.cost,
                 status=EXCLUDED.status, updated_at=EXCLUDED.updated_at""",
                (sku.sku_id, sku.tenant_id, sku.product_id, sku.merchant_sku,
                 _json(sku.variant_attributes), sku.cost, sku.status,
                 sku.created_at, sku.updated_at),
            )
        return sku

    def get_sku(self, tenant_id, sku_id):
        row = self._fetch_row(
            "SELECT * FROM commerce_skus WHERE tenant_id=%s AND sku_id=%s",
            (tenant_id, sku_id),
        )
        return SKU.from_dict(row) if row else None

    def list_skus_by_product(self, tenant_id, product_id):
        rows = self._fetch_rows(
            "SELECT * FROM commerce_skus WHERE tenant_id=%s AND product_id=%s "
            "ORDER BY sku_id", (tenant_id, product_id),
        )
        return [SKU.from_dict(row) for row in rows]

    def upsert_listing(self, tenant_id, listing):
        self._require_tenant(tenant_id, listing.tenant_id)
        self._verify_parent_tenant(tenant_id, "commerce_stores", "store_id", listing.store_id)
        with self._connection() as conn:
            self._execute(
                conn,
                """INSERT INTO commerce_listings
                (listing_id, tenant_id, store_id, platform, external_listing_id,
                 title, parent_external_id, status, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (listing_id) DO UPDATE SET
                 store_id=EXCLUDED.store_id, platform=EXCLUDED.platform,
                 external_listing_id=EXCLUDED.external_listing_id, title=EXCLUDED.title,
                 parent_external_id=EXCLUDED.parent_external_id, status=EXCLUDED.status,
                 updated_at=EXCLUDED.updated_at""",
                (listing.listing_id, listing.tenant_id, listing.store_id,
                 listing.platform, listing.external_listing_id, listing.title,
                 listing.parent_external_id, listing.status,
                 listing.created_at, listing.updated_at),
            )
        return listing

    def get_listing(self, tenant_id, listing_id):
        row = self._fetch_row(
            "SELECT * FROM commerce_listings WHERE tenant_id=%s AND listing_id=%s",
            (tenant_id, listing_id),
        )
        return Listing.from_dict(row) if row else None

    def list_listings_by_store(self, tenant_id, store_id):
        rows = self._fetch_rows(
            "SELECT * FROM commerce_listings WHERE tenant_id=%s AND store_id=%s "
            "ORDER BY listing_id", (tenant_id, store_id),
        )
        return [Listing.from_dict(row) for row in rows]

    def upsert_listing_item(self, tenant_id, item):
        self._verify_parent_tenant(tenant_id, "commerce_listings", "listing_id", item.listing_id)
        self._verify_parent_tenant(tenant_id, "commerce_skus", "sku_id", item.sku_id)
        with self._connection() as conn:
            self._execute(
                conn,
                """INSERT INTO commerce_listing_items
                (listing_item_id, tenant_id, listing_id, sku_id, external_sku_id,
                 variant_attributes, price, status, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                ON CONFLICT (listing_item_id) DO UPDATE SET
                 listing_id=EXCLUDED.listing_id, sku_id=EXCLUDED.sku_id,
                 external_sku_id=EXCLUDED.external_sku_id,
                 variant_attributes=EXCLUDED.variant_attributes, price=EXCLUDED.price,
                 status=EXCLUDED.status, updated_at=EXCLUDED.updated_at""",
                (item.listing_item_id, tenant_id, item.listing_id, item.sku_id,
                 item.external_sku_id, _json(item.variant_attributes), item.price,
                 item.status, item.updated_at),
            )
        return item

    def get_listing_item(self, tenant_id, listing_item_id):
        row = self._fetch_row(
            "SELECT * FROM commerce_listing_items WHERE tenant_id=%s AND listing_item_id=%s",
            (tenant_id, listing_item_id),
        )
        return ListingItem.from_dict(row) if row else None

    def list_listing_items_by_listing(self, tenant_id, listing_id):
        rows = self._fetch_rows(
            "SELECT * FROM commerce_listing_items WHERE tenant_id=%s AND listing_id=%s "
            "ORDER BY listing_item_id", (tenant_id, listing_id),
        )
        return [ListingItem.from_dict(row) for row in rows]

    # ── Inventory (append-only) ───────────────────────────────

    def append_inventory_snapshot(self, tenant_id, snapshot):
        self._require_tenant(tenant_id, snapshot.tenant_id)
        self._verify_parent_tenant(tenant_id, "commerce_stores", "store_id", snapshot.store_id)
        self._verify_parent_tenant(tenant_id, "commerce_skus", "sku_id", snapshot.sku_id)
        source = _inventory_source(snapshot)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO commerce_inventory_snapshots
                    (inventory_snapshot_id, tenant_id, store_id, sku_id, on_hand_quantity,
                     available_quantity, reserved_quantity, inbound_quantity, snapshot_at,
                     source, source_metadata)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                    ON CONFLICT (tenant_id, store_id, sku_id, snapshot_at, source)
                    DO NOTHING""",
                    (snapshot.inventory_snapshot_id, snapshot.tenant_id,
                     snapshot.store_id, snapshot.sku_id, snapshot.on_hand_quantity,
                     snapshot.available_quantity, snapshot.reserved_quantity,
                     snapshot.inbound_quantity, snapshot.snapshot_at, source,
                     _json(snapshot.source_metadata)),
                )
                return cursor.rowcount == 1

    def get_latest_inventory(self, tenant_id, store_id, sku_id):
        row = self._fetch_row(
            "SELECT * FROM commerce_inventory_snapshots WHERE tenant_id=%s "
            "AND store_id=%s AND sku_id=%s ORDER BY snapshot_at DESC, "
            "inventory_snapshot_id DESC LIMIT 1",
            (tenant_id, store_id, sku_id),
        )
        return InventorySnapshot.from_dict(row) if row else None

    def list_inventory_history(self, tenant_id, store_id, sku_id):
        rows = self._fetch_rows(
            "SELECT * FROM commerce_inventory_snapshots WHERE tenant_id=%s "
            "AND store_id=%s AND sku_id=%s ORDER BY snapshot_at",
            (tenant_id, store_id, sku_id),
        )
        return [InventorySnapshot.from_dict(row) for row in rows]

    # ── Advertising ───────────────────────────────────────────

    def upsert_campaign(self, tenant_id, campaign):
        self._require_tenant(tenant_id, campaign.tenant_id)
        self._verify_parent_tenant(tenant_id, "commerce_stores", "store_id", campaign.store_id)
        with self._connection() as conn:
            self._execute(
                conn,
                """INSERT INTO commerce_campaigns
                (campaign_id, tenant_id, store_id, platform, external_campaign_id,
                 name, campaign_type, objective, status, budget_type, daily_budget,
                 currency, start_at, end_at, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (campaign_id) DO UPDATE SET
                 store_id=EXCLUDED.store_id, platform=EXCLUDED.platform,
                 external_campaign_id=EXCLUDED.external_campaign_id, name=EXCLUDED.name,
                 campaign_type=EXCLUDED.campaign_type, objective=EXCLUDED.objective,
                 status=EXCLUDED.status, budget_type=EXCLUDED.budget_type,
                 daily_budget=EXCLUDED.daily_budget, currency=EXCLUDED.currency,
                 start_at=EXCLUDED.start_at, end_at=EXCLUDED.end_at,
                 updated_at=EXCLUDED.updated_at""",
                (campaign.campaign_id, campaign.tenant_id, campaign.store_id,
                 campaign.platform, campaign.external_campaign_id, campaign.name,
                 campaign.campaign_type, campaign.objective, campaign.status,
                 campaign.budget_type, campaign.daily_budget, campaign.currency,
                 campaign.start_at, campaign.end_at, campaign.created_at,
                 campaign.updated_at),
            )
        return campaign

    def get_campaign(self, tenant_id, campaign_id):
        row = self._fetch_row(
            "SELECT * FROM commerce_campaigns WHERE tenant_id=%s AND campaign_id=%s",
            (tenant_id, campaign_id),
        )
        return Campaign.from_dict(row) if row else None

    def list_campaigns_by_store(self, tenant_id, store_id):
        rows = self._fetch_rows(
            "SELECT * FROM commerce_campaigns WHERE tenant_id=%s AND store_id=%s "
            "ORDER BY campaign_id", (tenant_id, store_id),
        )
        return [Campaign.from_dict(row) for row in rows]

    def upsert_ad_group(self, tenant_id, ad_group):
        self._verify_parent_tenant(tenant_id, "commerce_campaigns", "campaign_id", ad_group.campaign_id)
        with self._connection() as conn:
            self._execute(
                conn,
                """INSERT INTO commerce_ad_groups
                (ad_group_id, tenant_id, campaign_id, external_ad_group_id, name,
                 status, default_bid, targeting_type, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (ad_group_id) DO UPDATE SET
                 campaign_id=EXCLUDED.campaign_id,
                 external_ad_group_id=EXCLUDED.external_ad_group_id, name=EXCLUDED.name,
                 status=EXCLUDED.status, default_bid=EXCLUDED.default_bid,
                 targeting_type=EXCLUDED.targeting_type, updated_at=EXCLUDED.updated_at""",
                (ad_group.ad_group_id, tenant_id, ad_group.campaign_id,
                 ad_group.external_ad_group_id, ad_group.name, ad_group.status,
                 ad_group.default_bid, ad_group.targeting_type,
                 ad_group.created_at, ad_group.updated_at),
            )
        return ad_group

    def list_ad_groups_by_campaign(self, tenant_id, campaign_id):
        rows = self._fetch_rows(
            "SELECT * FROM commerce_ad_groups WHERE tenant_id=%s AND campaign_id=%s "
            "ORDER BY ad_group_id", (tenant_id, campaign_id),
        )
        return [AdGroup.from_dict(row) for row in rows]

    def upsert_ad(self, tenant_id, ad):
        self._verify_parent_tenant(tenant_id, "commerce_ad_groups", "ad_group_id", ad.ad_group_id)
        with self._connection() as conn:
            self._execute(
                conn,
                """INSERT INTO commerce_ads
                (ad_id, tenant_id, ad_group_id, external_ad_id, ad_type, creative_ref,
                 status, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (ad_id) DO UPDATE SET
                 ad_group_id=EXCLUDED.ad_group_id, external_ad_id=EXCLUDED.external_ad_id,
                 ad_type=EXCLUDED.ad_type, creative_ref=EXCLUDED.creative_ref,
                 status=EXCLUDED.status, updated_at=EXCLUDED.updated_at""",
                (ad.ad_id, tenant_id, ad.ad_group_id, ad.external_ad_id, ad.ad_type,
                 ad.creative_ref, ad.status, ad.created_at, ad.updated_at),
            )
        return ad

    def list_ads_by_ad_group(self, tenant_id, ad_group_id):
        rows = self._fetch_rows(
            "SELECT * FROM commerce_ads WHERE tenant_id=%s AND ad_group_id=%s "
            "ORDER BY ad_id", (tenant_id, ad_group_id),
        )
        return [Ad.from_dict(row) for row in rows]

    def upsert_ad_promoted_item(self, tenant_id, item):
        self._verify_parent_tenant(tenant_id, "commerce_ads", "ad_id", item.ad_id)
        self._verify_parent_tenant(tenant_id, "commerce_listings", "listing_id", item.listing_id)
        with self._connection() as conn:
            self._execute(
                conn,
                """INSERT INTO commerce_ad_promoted_items
                (ad_promoted_item_id, tenant_id, ad_id, listing_id, listing_item_id)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (ad_promoted_item_id) DO UPDATE SET
                 ad_id=EXCLUDED.ad_id, listing_id=EXCLUDED.listing_id,
                 listing_item_id=EXCLUDED.listing_item_id""",
                (item.ad_promoted_item_id, tenant_id, item.ad_id, item.listing_id,
                 item.listing_item_id),
            )
        return item

    def list_promoted_items_by_ad(self, tenant_id, ad_id):
        rows = self._fetch_rows(
            "SELECT * FROM commerce_ad_promoted_items WHERE tenant_id=%s AND ad_id=%s "
            "ORDER BY ad_promoted_item_id", (tenant_id, ad_id),
        )
        return [AdPromotedItem.from_dict(row) for row in rows]

    def upsert_keyword(self, tenant_id, keyword):
        self._verify_parent_tenant(tenant_id, "commerce_ad_groups", "ad_group_id", keyword.ad_group_id)
        with self._connection() as conn:
            self._execute(
                conn,
                """INSERT INTO commerce_keywords
                (keyword_id, tenant_id, ad_group_id, external_keyword_id, keyword_text,
                 match_type, bid, status, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (keyword_id) DO UPDATE SET
                 ad_group_id=EXCLUDED.ad_group_id,
                 external_keyword_id=EXCLUDED.external_keyword_id,
                 keyword_text=EXCLUDED.keyword_text, match_type=EXCLUDED.match_type,
                 bid=EXCLUDED.bid, status=EXCLUDED.status""",
                (keyword.keyword_id, tenant_id, keyword.ad_group_id,
                 keyword.external_keyword_id, keyword.keyword_text, keyword.match_type,
                 keyword.bid, keyword.status, keyword.created_at),
            )
        return keyword

    def list_keywords_by_ad_group(self, tenant_id, ad_group_id):
        rows = self._fetch_rows(
            "SELECT * FROM commerce_keywords WHERE tenant_id=%s AND ad_group_id=%s "
            "ORDER BY keyword_id", (tenant_id, ad_group_id),
        )
        return [Keyword.from_dict(row) for row in rows]

    def upsert_search_term(self, tenant_id, term):
        self._verify_parent_tenant(tenant_id, "commerce_ad_groups", "ad_group_id", term.ad_group_id)
        with self._connection() as conn:
            self._execute(
                conn,
                """INSERT INTO commerce_search_terms
                (search_term_id, tenant_id, ad_group_id, keyword_id, search_term,
                 observed_date, dimensions)
                VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT (search_term_id) DO UPDATE SET
                 ad_group_id=EXCLUDED.ad_group_id, keyword_id=EXCLUDED.keyword_id,
                 search_term=EXCLUDED.search_term, observed_date=EXCLUDED.observed_date,
                 dimensions=EXCLUDED.dimensions""",
                (term.search_term_id, tenant_id, term.ad_group_id, term.keyword_id,
                 term.search_term, term.observed_date, _json(term.dimensions)),
            )
        return term

    def list_search_terms_by_ad_group(self, tenant_id, ad_group_id):
        rows = self._fetch_rows(
            "SELECT * FROM commerce_search_terms WHERE tenant_id=%s AND ad_group_id=%s "
            "ORDER BY search_term_id", (tenant_id, ad_group_id),
        )
        return [SearchTerm.from_dict(row) for row in rows]

    # ── Review / ReviewInsight ────────────────────────────────

    def upsert_review(self, tenant_id, review):
        self._require_tenant(tenant_id, review.tenant_id)
        self._verify_parent_tenant(tenant_id, "commerce_stores", "store_id", review.store_id)
        self._verify_parent_tenant(tenant_id, "commerce_listings", "listing_id", review.listing_id)
        with self._connection() as conn:
            self._execute(
                conn,
                """INSERT INTO commerce_reviews
                (review_id, tenant_id, store_id, listing_id, listing_item_id, platform,
                 external_review_id, rating, title, content, language, verified_purchase,
                 review_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (review_id) DO UPDATE SET
                 store_id=EXCLUDED.store_id, listing_id=EXCLUDED.listing_id,
                 listing_item_id=EXCLUDED.listing_item_id, platform=EXCLUDED.platform,
                 external_review_id=EXCLUDED.external_review_id, rating=EXCLUDED.rating,
                 title=EXCLUDED.title, content=EXCLUDED.content, language=EXCLUDED.language,
                 verified_purchase=EXCLUDED.verified_purchase, review_at=EXCLUDED.review_at,
                 updated_at=EXCLUDED.updated_at""",
                (review.review_id, review.tenant_id, review.store_id, review.listing_id,
                 review.listing_item_id, review.platform, review.external_review_id,
                 review.rating, review.title, review.content, review.language,
                 review.verified_purchase, review.review_at, review.updated_at),
            )
        return review

    def get_review(self, tenant_id, review_id):
        row = self._fetch_row(
            "SELECT * FROM commerce_reviews WHERE tenant_id=%s AND review_id=%s",
            (tenant_id, review_id),
        )
        return Review.from_dict(row) if row else None

    def list_reviews_by_listing(self, tenant_id, listing_id):
        rows = self._fetch_rows(
            "SELECT * FROM commerce_reviews WHERE tenant_id=%s AND listing_id=%s "
            "ORDER BY review_id", (tenant_id, listing_id),
        )
        return [Review.from_dict(row) for row in rows]

    def upsert_review_insight(self, tenant_id, insight):
        self._verify_parent_tenant(tenant_id, "commerce_reviews", "review_id", insight.review_id)
        with self._connection() as conn:
            self._execute(
                conn,
                """INSERT INTO commerce_review_insights
                (review_insight_id, tenant_id, review_id, sentiment, topics, issues,
                 strengths, intent, severity, confidence, model_provider, model_version,
                 extractor_version, generated_at, supersedes_id)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (review_insight_id) DO UPDATE SET
                 review_id=EXCLUDED.review_id, sentiment=EXCLUDED.sentiment,
                 topics=EXCLUDED.topics, issues=EXCLUDED.issues,
                 strengths=EXCLUDED.strengths, intent=EXCLUDED.intent,
                 severity=EXCLUDED.severity, confidence=EXCLUDED.confidence,
                 model_provider=EXCLUDED.model_provider,
                 model_version=EXCLUDED.model_version,
                 extractor_version=EXCLUDED.extractor_version,
                 generated_at=EXCLUDED.generated_at, supersedes_id=EXCLUDED.supersedes_id""",
                (insight.review_insight_id, tenant_id, insight.review_id,
                 insight.sentiment, _json(list(insight.topics)),
                 _json(list(insight.issues)), _json(list(insight.strengths)),
                 insight.intent, insight.severity, insight.confidence,
                 insight.model_provider, insight.model_version,
                 insight.extractor_version, insight.generated_at,
                 insight.supersedes_id),
            )
        return insight

    def list_review_insights_by_review(self, tenant_id, review_id):
        rows = self._fetch_rows(
            "SELECT * FROM commerce_review_insights WHERE tenant_id=%s AND review_id=%s "
            "ORDER BY review_insight_id", (tenant_id, review_id),
        )
        return [ReviewInsight.from_dict(row) for row in rows]

    # ── Metric (natural-key idempotent) ───────────────────────

    def upsert_metric(self, tenant_id, series):
        self._require_tenant(tenant_id, series.tenant_id)
        dimensions_hash = _metric_dimensions_hash(series)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO commerce_metric_series
                    (metric_record_id, tenant_id, subject_type, subject_id, metric_name,
                     metric_class, granularity, period_start, period_end, value, unit,
                     dimensions, dimensions_hash, source_metadata, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s)
                    ON CONFLICT (tenant_id, subject_type, subject_id, metric_name,
                      period_start, period_end, granularity, dimensions_hash)
                    DO UPDATE SET
                     value=EXCLUDED.value, unit=EXCLUDED.unit,
                     source_metadata=EXCLUDED.source_metadata,
                     updated_at=EXCLUDED.updated_at""",
                    (series.metric_record_id, series.tenant_id, series.subject_type,
                     series.subject_id, series.metric_name, series.metric_class,
                     series.granularity, series.period_start, series.period_end,
                     series.value, series.unit, _json(series.dimensions),
                     dimensions_hash, _json(series.source_metadata),
                     series.updated_at),
                )
        # Return the canonical row so the caller observes the stable id.
        rows = self.query_metrics(
            tenant_id, series.subject_type, series.subject_id,
            [series.metric_name], series.granularity,
            series.period_start, series.period_end,
        )
        matches = [r for r in rows if r.dimensions_hash == dimensions_hash]
        return matches[0] if matches else series

    def query_metrics(self, tenant_id, subject_type, subject_id,
                      metric_names=None, granularity=None,
                      period_start=None, period_end=None):
        clauses = ["tenant_id=%s", "subject_type=%s", "subject_id=%s"]
        params = [tenant_id, subject_type, subject_id]
        if metric_names:
            clauses.append("metric_name = ANY(%s)")
            params.append(list(metric_names))
        if granularity:
            clauses.append("granularity=%s")
            params.append(granularity)
        if period_start:
            clauses.append("period_end > %s")
            params.append(period_start)
        if period_end:
            clauses.append("period_start <= %s")
            params.append(period_end)
        sql = ("SELECT * FROM commerce_metric_series WHERE "
               + " AND ".join(clauses) + " ORDER BY period_start, metric_name")
        rows = self._fetch_rows(sql, tuple(params))
        return [MetricSeries.from_dict(row) for row in rows]

    # ── Internal helpers ──────────────────────────────────────

    @staticmethod
    def _require_tenant(tenant_id, entity_tenant_id):
        if entity_tenant_id is not None and entity_tenant_id != tenant_id:
            raise TenantIsolationViolation(
                f"cross-tenant write denied: expected {tenant_id!r}, "
                f"got {entity_tenant_id!r}"
            )

    def _verify_parent_tenant(self, tenant_id, table, id_column, parent_id):
        if parent_id is None:
            raise CommerceStorageError(
                f"parent reference is required: {table}.{id_column}"
            )
        row = self._fetch_row(
            f"SELECT tenant_id FROM {table} WHERE {id_column}=%s", (parent_id,),
        )
        if row is None:
            raise CommerceStorageError(
                f"parent not found: {table}.{id_column}={parent_id!r}"
            )
        self._require_tenant(tenant_id, row["tenant_id"])

    @contextmanager
    def _connection(self):
        with self.connection_factory() as connection:
            yield connection

    @staticmethod
    def _execute(conn, sql, params):
        with conn.cursor() as cursor:
            cursor.execute(sql, params)

    def _fetch_row(self, sql, params):
        rows = self._fetch_rows(sql, params)
        return rows[0] if rows else None

    def _fetch_rows(self, sql, params):
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                columns = [description.name for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
