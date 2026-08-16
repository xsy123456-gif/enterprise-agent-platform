"""Canonical commerce PostgreSQL schema (idempotent).

Follows the memory schema convention: ``CREATE TABLE IF NOT EXISTS`` for every
table, composite UNIQUE constraints for natural keys, and a validation step
that checks the expected tables/columns exist.  Every table carries a
``tenant_id`` column (denormalized for nested entities) so tenant isolation is
enforced at the storage boundary without multi-hop joins.
"""

TABLES = {
    "commerce_stores",
    "commerce_products",
    "commerce_skus",
    "commerce_listings",
    "commerce_listing_items",
    "commerce_inventory_snapshots",
    "commerce_campaigns",
    "commerce_ad_groups",
    "commerce_ads",
    "commerce_ad_promoted_items",
    "commerce_keywords",
    "commerce_search_terms",
    "commerce_reviews",
    "commerce_review_insights",
    "commerce_metric_series",
    "commerce_external_identities",
}

REQUIRED_COLUMNS = {
    "commerce_stores": {
        "store_id", "tenant_id", "platform", "marketplace", "external_store_id",
        "name", "currency", "timezone", "status", "created_at", "updated_at",
    },
    "commerce_products": {
        "product_id", "tenant_id", "title", "brand", "category", "product_type",
        "attributes", "status", "created_at", "updated_at",
    },
    "commerce_skus": {
        "sku_id", "tenant_id", "product_id", "merchant_sku",
        "variant_attributes", "cost", "status", "created_at", "updated_at",
    },
    "commerce_listings": {
        "listing_id", "tenant_id", "store_id", "platform", "external_listing_id",
        "parent_external_id", "title", "status", "created_at", "updated_at",
    },
    "commerce_listing_items": {
        "listing_item_id", "tenant_id", "listing_id", "sku_id", "external_sku_id",
        "variant_attributes", "price", "status", "updated_at",
    },
    "commerce_inventory_snapshots": {
        "inventory_snapshot_id", "tenant_id", "store_id", "sku_id",
        "on_hand_quantity", "available_quantity", "reserved_quantity",
        "inbound_quantity", "snapshot_at", "source", "source_metadata",
    },
    "commerce_campaigns": {
        "campaign_id", "tenant_id", "store_id", "platform",
        "external_campaign_id", "name", "campaign_type", "objective", "status",
        "budget_type", "daily_budget", "currency", "start_at", "end_at",
        "created_at", "updated_at",
    },
    "commerce_ad_groups": {
        "ad_group_id", "tenant_id", "campaign_id", "external_ad_group_id",
        "name", "status", "default_bid", "targeting_type", "created_at", "updated_at",
    },
    "commerce_ads": {
        "ad_id", "tenant_id", "ad_group_id", "external_ad_id", "ad_type",
        "creative_ref", "status", "created_at", "updated_at",
    },
    "commerce_ad_promoted_items": {
        "ad_promoted_item_id", "tenant_id", "ad_id", "listing_id", "listing_item_id",
    },
    "commerce_keywords": {
        "keyword_id", "tenant_id", "ad_group_id", "external_keyword_id",
        "keyword_text", "match_type", "bid", "status", "created_at",
    },
    "commerce_search_terms": {
        "search_term_id", "tenant_id", "ad_group_id", "keyword_id",
        "search_term", "observed_date", "dimensions",
    },
    "commerce_reviews": {
        "review_id", "tenant_id", "store_id", "listing_id", "listing_item_id",
        "platform", "external_review_id", "rating", "title", "content",
        "language", "verified_purchase", "review_at", "updated_at",
    },
    "commerce_review_insights": {
        "review_insight_id", "tenant_id", "review_id", "sentiment", "topics",
        "issues", "strengths", "intent", "severity", "confidence",
        "model_provider", "model_version", "extractor_version", "generated_at",
        "supersedes_id", "extractor_id", "prompt_version",
        "knowledge_policy_version", "knowledge_context_version",
    },
    "commerce_metric_series": {
        "metric_record_id", "tenant_id", "subject_type", "subject_id",
        "metric_name", "metric_class", "granularity", "period_start",
        "period_end", "value", "unit", "dimensions", "dimensions_hash",
        "source_metadata", "updated_at",
    },
    "commerce_external_identities": {
        "tenant_id", "platform", "store_id", "resource_type", "external_id",
        "canonical_id",
    },
}

# Natural-key columns used for idempotent upsert / append semantics.
METRIC_NATURAL_KEY = (
    "tenant_id", "subject_type", "subject_id", "metric_name",
    "period_start", "period_end", "granularity", "dimensions_hash",
)
INVENTORY_NATURAL_KEY = (
    "tenant_id", "store_id", "sku_id", "snapshot_at", "source",
)
EXTERNAL_IDENTITY_NATURAL_KEY = (
    "tenant_id", "platform", "store_id", "resource_type", "external_id",
)


def build_schema_sql() -> str:
    return """
CREATE TABLE IF NOT EXISTS commerce_stores (
  store_id text PRIMARY KEY, tenant_id text NOT NULL, platform text NOT NULL,
  marketplace text NOT NULL, external_store_id text NOT NULL, name text NOT NULL,
  currency text NOT NULL, timezone text NOT NULL, status text NOT NULL,
  created_at text NOT NULL, updated_at text NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS commerce_stores_external_uidx
  ON commerce_stores (tenant_id, platform, external_store_id);

CREATE TABLE IF NOT EXISTS commerce_products (
  product_id text PRIMARY KEY, tenant_id text NOT NULL, title text NOT NULL,
  brand text NOT NULL DEFAULT '', category text NOT NULL DEFAULT '',
  product_type text NOT NULL DEFAULT '', attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL, created_at text NOT NULL, updated_at text NOT NULL
);

CREATE TABLE IF NOT EXISTS commerce_skus (
  sku_id text PRIMARY KEY, tenant_id text NOT NULL, product_id text NOT NULL,
  merchant_sku text NOT NULL, variant_attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
  cost double precision, status text NOT NULL,
  created_at text NOT NULL, updated_at text NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS commerce_skus_merchant_uidx
  ON commerce_skus (tenant_id, merchant_sku);

CREATE TABLE IF NOT EXISTS commerce_listings (
  listing_id text PRIMARY KEY, tenant_id text NOT NULL, store_id text NOT NULL,
  platform text NOT NULL, external_listing_id text NOT NULL, title text NOT NULL DEFAULT '',
  parent_external_id text, status text NOT NULL,
  created_at text NOT NULL, updated_at text NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS commerce_listings_external_uidx
  ON commerce_listings (tenant_id, store_id, external_listing_id);

CREATE TABLE IF NOT EXISTS commerce_listing_items (
  listing_item_id text PRIMARY KEY, tenant_id text NOT NULL, listing_id text NOT NULL,
  sku_id text NOT NULL, external_sku_id text NOT NULL,
  variant_attributes jsonb NOT NULL DEFAULT '{}'::jsonb, price double precision,
  status text NOT NULL, updated_at text NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS commerce_listing_items_external_uidx
  ON commerce_listing_items (tenant_id, listing_id, external_sku_id);

CREATE TABLE IF NOT EXISTS commerce_inventory_snapshots (
  inventory_snapshot_id text PRIMARY KEY, tenant_id text NOT NULL,
  store_id text NOT NULL, sku_id text NOT NULL, on_hand_quantity integer NOT NULL DEFAULT 0,
  available_quantity integer NOT NULL DEFAULT 0,
  reserved_quantity integer NOT NULL DEFAULT 0,
  inbound_quantity integer NOT NULL DEFAULT 0, snapshot_at text NOT NULL,
  source text NOT NULL, source_metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE UNIQUE INDEX IF NOT EXISTS commerce_inventory_natural_uidx
  ON commerce_inventory_snapshots (tenant_id, store_id, sku_id, snapshot_at, source);

CREATE TABLE IF NOT EXISTS commerce_campaigns (
  campaign_id text PRIMARY KEY, tenant_id text NOT NULL, store_id text NOT NULL,
  platform text NOT NULL, external_campaign_id text NOT NULL, name text NOT NULL,
  campaign_type text NOT NULL DEFAULT 'OTHER', objective text NOT NULL DEFAULT 'OTHER',
  status text NOT NULL, budget_type text NOT NULL DEFAULT '',
  daily_budget double precision, currency text NOT NULL DEFAULT '',
  start_at text, end_at text,
  created_at text NOT NULL, updated_at text NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS commerce_campaigns_external_uidx
  ON commerce_campaigns (tenant_id, external_campaign_id);

CREATE TABLE IF NOT EXISTS commerce_ad_groups (
  ad_group_id text PRIMARY KEY, tenant_id text NOT NULL, campaign_id text NOT NULL,
  external_ad_group_id text NOT NULL, name text NOT NULL, status text NOT NULL,
  default_bid double precision, targeting_type text NOT NULL DEFAULT 'OTHER',
  created_at text NOT NULL, updated_at text NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS commerce_ad_groups_external_uidx
  ON commerce_ad_groups (tenant_id, campaign_id, external_ad_group_id);

CREATE TABLE IF NOT EXISTS commerce_ads (
  ad_id text PRIMARY KEY, tenant_id text NOT NULL, ad_group_id text NOT NULL,
  external_ad_id text NOT NULL, ad_type text NOT NULL DEFAULT 'OTHER',
  creative_ref text, status text NOT NULL,
  created_at text NOT NULL, updated_at text NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS commerce_ads_external_uidx
  ON commerce_ads (tenant_id, ad_group_id, external_ad_id);

CREATE TABLE IF NOT EXISTS commerce_ad_promoted_items (
  ad_promoted_item_id text PRIMARY KEY, tenant_id text NOT NULL, ad_id text NOT NULL,
  listing_id text NOT NULL, listing_item_id text
);
CREATE UNIQUE INDEX IF NOT EXISTS commerce_ad_promoted_items_uidx
  ON commerce_ad_promoted_items (tenant_id, ad_id, listing_id, listing_item_id);

CREATE TABLE IF NOT EXISTS commerce_keywords (
  keyword_id text PRIMARY KEY, tenant_id text NOT NULL, ad_group_id text NOT NULL,
  external_keyword_id text NOT NULL, keyword_text text NOT NULL,
  match_type text NOT NULL DEFAULT 'OTHER', bid double precision,
  status text NOT NULL, created_at text NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS commerce_keywords_external_uidx
  ON commerce_keywords (tenant_id, ad_group_id, external_keyword_id);

CREATE TABLE IF NOT EXISTS commerce_search_terms (
  search_term_id text PRIMARY KEY, tenant_id text NOT NULL, ad_group_id text NOT NULL,
  keyword_id text, search_term text NOT NULL, observed_date text,
  dimensions jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS commerce_reviews (
  review_id text PRIMARY KEY, tenant_id text NOT NULL, store_id text NOT NULL,
  listing_id text NOT NULL, listing_item_id text, platform text NOT NULL,
  external_review_id text NOT NULL, rating double precision NOT NULL,
  title text NOT NULL DEFAULT '', content text NOT NULL DEFAULT '',
  language text NOT NULL DEFAULT '', verified_purchase boolean NOT NULL DEFAULT false,
  review_at text, updated_at text NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS commerce_reviews_external_uidx
  ON commerce_reviews (tenant_id, external_review_id);

CREATE TABLE IF NOT EXISTS commerce_review_insights (
  review_insight_id text PRIMARY KEY, tenant_id text NOT NULL, review_id text NOT NULL,
  sentiment text NOT NULL DEFAULT '', topics jsonb NOT NULL DEFAULT '[]'::jsonb,
  issues jsonb NOT NULL DEFAULT '[]'::jsonb, strengths jsonb NOT NULL DEFAULT '[]'::jsonb,
  intent text NOT NULL DEFAULT '', severity text NOT NULL DEFAULT '',
  confidence double precision, model_provider text NOT NULL DEFAULT '',
  model_version text NOT NULL DEFAULT '', extractor_version text NOT NULL DEFAULT '',
  extractor_id text NOT NULL DEFAULT '', prompt_version text NOT NULL DEFAULT '',
  knowledge_policy_version text NOT NULL DEFAULT '',
  knowledge_context_version text NOT NULL DEFAULT '',
  generated_at text NOT NULL, supersedes_id text
);
CREATE UNIQUE INDEX IF NOT EXISTS commerce_review_insights_natural_uidx
  ON commerce_review_insights (tenant_id, review_id, extractor_id, extractor_version);

CREATE TABLE IF NOT EXISTS commerce_metric_series (
  metric_record_id text PRIMARY KEY, tenant_id text NOT NULL,
  subject_type text NOT NULL, subject_id text NOT NULL, metric_name text NOT NULL,
  metric_class text NOT NULL, granularity text NOT NULL,
  period_start text NOT NULL, period_end text NOT NULL,
  value double precision NOT NULL, unit text NOT NULL DEFAULT '',
  dimensions jsonb NOT NULL DEFAULT '{}'::jsonb, dimensions_hash text NOT NULL DEFAULT '',
  source_metadata jsonb NOT NULL DEFAULT '{}'::jsonb, updated_at text NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS commerce_metric_natural_uidx
  ON commerce_metric_series (tenant_id, subject_type, subject_id, metric_name,
    period_start, period_end, granularity, dimensions_hash);
CREATE INDEX IF NOT EXISTS commerce_metric_subject_idx
  ON commerce_metric_series (tenant_id, subject_type, subject_id, metric_name, granularity);

CREATE TABLE IF NOT EXISTS commerce_external_identities (
  tenant_id text NOT NULL, platform text NOT NULL, store_id text NOT NULL,
  resource_type text NOT NULL, external_id text NOT NULL, canonical_id text NOT NULL,
  PRIMARY KEY (tenant_id, platform, store_id, resource_type, external_id)
);
"""
