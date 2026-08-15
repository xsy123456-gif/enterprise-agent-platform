"""Commerce Query Service.

The single read boundary above the canonical store.  ``tenant_id`` is always
the *trusted* tenant from the execution context; the service never derives it
from request data.  Every response is a ``QueryResult`` carrying freshness,
quality and provenance metadata.

Responsibilities (v1):

- resolve external ids to canonical ids via the identity map;
- read Store / Catalog / Inventory / Review / Advertising *facts*;
- return stored SOURCE / AGGREGATED metric records only.

Explicitly NOT done here (deferred to later phases):

- DERIVED metric computation (ROAS / CVR / CPC / AOV / DaysOfSupply ...);
- period comparison (current vs baseline);
- anomaly / trend detection;
- root cause reasoning or priority assignment.
"""

import uuid

from app.commerce.contracts.query import PageInfo, QueryResult
from app.commerce.domain.base import utc_now
from app.commerce.query.freshness import (
    FreshnessPolicy,
    STANDARD_READ_POLICY,
    evaluate_freshness,
)
from app.commerce.query.provenance import canonical_provenance
from app.commerce.query.quality import evaluate_quality


class CommerceQueryService:

    def __init__(self, repository, identity_map=None, freshness_policy=None,
                 canonical_schema_version="1.0"):
        self.repository = repository
        self.identity_map = identity_map
        self.freshness_policy = freshness_policy or STANDARD_READ_POLICY
        self.canonical_schema_version = canonical_schema_version

    # ── External resolution ───────────────────────────────────

    def resolve_subject(self, tenant_id, platform, store_id, resource_type, external_id):
        if self.identity_map is None:
            return None
        return self.identity_map.resolve(
            tenant_id, platform, store_id, resource_type, external_id
        )

    # ── Store ─────────────────────────────────────────────────

    def get_store(self, tenant_id, store_id, request_id=None):
        store = self.repository.get_store(tenant_id, store_id)
        return self._assemble(tenant_id, [store] if store else [], "updated_at", request_id)

    def find_store_by_external(self, tenant_id, platform, external_store_id, request_id=None):
        store = self.repository.find_store_by_external(tenant_id, platform, external_store_id)
        return self._assemble(tenant_id, [store] if store else [], "updated_at", request_id)

    def resolve_store_id_by_external(self, tenant_id, platform, external_store_id):
        return self.repository.resolve_store_id_by_external(
            tenant_id, platform, external_store_id
        )

    # ── Catalog ───────────────────────────────────────────────

    def list_products(self, tenant_id, request_id=None):
        products = self.repository.list_products(tenant_id)
        return self._assemble(tenant_id, products, "updated_at", request_id)

    def list_skus_by_product(self, tenant_id, product_id, request_id=None):
        skus = self.repository.list_skus_by_product(tenant_id, product_id)
        return self._assemble(tenant_id, skus, "updated_at", request_id)

    def list_listings_by_store(self, tenant_id, store_id, request_id=None):
        listings = self.repository.list_listings_by_store(tenant_id, store_id)
        return self._assemble(tenant_id, listings, "updated_at", request_id)

    # ── Metric ────────────────────────────────────────────────

    def query_metrics(self, tenant_id, subject_type, subject_id, metric_names=None,
                      granularity=None, time_range=None, request_id=None):
        period_start = time_range.start if time_range else None
        period_end = time_range.end if time_range else None
        series = self.repository.query_metrics(
            tenant_id, subject_type, subject_id, metric_names=metric_names,
            granularity=granularity, period_start=period_start, period_end=period_end,
        )
        return self._assemble(tenant_id, series, "updated_at", request_id)

    # ── Inventory ─────────────────────────────────────────────

    def query_inventory(self, tenant_id, store_id, sku_id, request_id=None):
        snapshots = self.repository.list_inventory_history(tenant_id, store_id, sku_id)
        return self._assemble(tenant_id, snapshots, "snapshot_at", request_id)

    def get_latest_inventory(self, tenant_id, store_id, sku_id, request_id=None):
        snapshot = self.repository.get_latest_inventory(tenant_id, store_id, sku_id)
        return self._assemble(tenant_id, [snapshot] if snapshot else [], "snapshot_at", request_id)

    # ── Review ────────────────────────────────────────────────

    def list_reviews_by_listing(self, tenant_id, listing_id, request_id=None):
        reviews = self.repository.list_reviews_by_listing(tenant_id, listing_id)
        return self._assemble(tenant_id, reviews, "updated_at", request_id)

    def list_review_insights_by_review(self, tenant_id, review_id, request_id=None):
        insights = self.repository.list_review_insights_by_review(tenant_id, review_id)
        return self._assemble(tenant_id, insights, "generated_at", request_id)

    # ── Advertising ───────────────────────────────────────────

    def list_campaigns_by_store(self, tenant_id, store_id, request_id=None):
        campaigns = self.repository.list_campaigns_by_store(tenant_id, store_id)
        return self._assemble(tenant_id, campaigns, "updated_at", request_id)

    def list_ad_groups_by_campaign(self, tenant_id, campaign_id, request_id=None):
        groups = self.repository.list_ad_groups_by_campaign(tenant_id, campaign_id)
        return self._assemble(tenant_id, groups, "updated_at", request_id)

    def list_ads_by_ad_group(self, tenant_id, ad_group_id, request_id=None):
        ads = self.repository.list_ads_by_ad_group(tenant_id, ad_group_id)
        return self._assemble(tenant_id, ads, "updated_at", request_id)

    def list_promoted_items_by_ad(self, tenant_id, ad_id, request_id=None):
        items = self.repository.list_promoted_items_by_ad(tenant_id, ad_id)
        return self._assemble(tenant_id, items, "updated_at", request_id)

    def list_keywords_by_ad_group(self, tenant_id, ad_group_id, request_id=None):
        keywords = self.repository.list_keywords_by_ad_group(tenant_id, ad_group_id)
        return self._assemble(tenant_id, keywords, "updated_at", request_id)

    def list_search_terms_by_ad_group(self, tenant_id, ad_group_id, request_id=None):
        terms = self.repository.list_search_terms_by_ad_group(tenant_id, ad_group_id)
        return self._assemble(tenant_id, terms, "updated_at", request_id)

    def list_listing_items_by_listing(self, tenant_id, listing_id, request_id=None):
        items = self.repository.list_listing_items_by_listing(tenant_id, listing_id)
        return self._assemble(tenant_id, items, "updated_at", request_id)

    # ── Assembly ──────────────────────────────────────────────

    def _assemble(self, tenant_id, data, fresh_field, request_id=None):
        records = [r for r in data if r is not None]
        last_synced = max(
            (getattr(r, fresh_field, None) for r in records),
            default=None,
        )
        quality = evaluate_quality(records, validator_version=self.canonical_schema_version)
        return QueryResult(
            request_id=request_id or uuid.uuid4().hex,
            data=tuple(records),
            page=PageInfo(returned_count=len(records), has_more=False),
            effective_scope={"tenant_id": tenant_id},
            freshness=evaluate_freshness(self.freshness_policy, last_synced),
            quality=quality,
            provenance=canonical_provenance(self.canonical_schema_version),
            executed_at=utc_now(),
        )


__all__ = ["CommerceQueryService"]
