"""Seven governed commerce read tools.

Each tool is a ``BaseTool`` that reads canonical commerce facts through the
``CommerceQueryService`` (the only data access layer).  Tools enforce the STRICT
scope policy against the Runtime-injected trusted context BEFORE any canonical
query, and use the typed Filter / TimeRange / Cursor Pagination / QueryResult /
ToolError contracts.  metric.query only serves SOURCE/AGGREGATED facts;
inventory.query returns inventory facts only; advertising.query returns
advertising *entities* only; review.query defaults to ``include_raw=false``;
review_insight.query serves AI facts only (issues/topics/confidence/severity +
provenance, never Cause/Impact/Priority).

Pagination uses a single shared cursor codec (``app.commerce.cursor``):
malformed / cross-resource cursors and over-limit pages fail with a typed
INVALID_REQUEST before any canonical query.
"""

import uuid

from app.tools.base import BaseTool

from app.commerce.contracts.errors import CommerceValidationError, ToolError
from app.commerce.contracts.query import Filter, PageInfo, PageRequest, QueryResult, TimeRange
from app.commerce.cursor import decode_cursor, paginate, validate_page
from app.commerce.trusted_context import current_trusted_context, store_in_scope


class CommerceReadTool(BaseTool):
    """Base class: STRICT scope + typed validation + query-service delegation."""

    name = ""
    capability = ""
    scope_policy = "STRICT"
    allowed_filter_fields = frozenset()
    paginated = True

    def __init__(self, query_service, allowed_filter_fields=None):
        self.query_service = query_service
        if allowed_filter_fields is not None:
            self.allowed_filter_fields = frozenset(allowed_filter_fields)

    # ── ToolRunner entrypoint ────────────────────────────────

    def execute(self, arguments):
        arguments = arguments or {}
        trusted = current_trusted_context()
        if trusted is None or not trusted.tenant_id:
            return ToolError.from_code(
                "PERMISSION_DENIED", message_key="missing trusted context",
                details_safe={"reason": "no trusted execution context"},
            )
        try:
            self._validate(arguments)
            self._validate_pagination(arguments)
        except CommerceValidationError as error:
            return ToolError.from_code(
                "INVALID_REQUEST", message_key=str(error),
                details_safe={"reason": str(error)},
            )
        denied = self._check_scope(arguments, trusted)
        if denied is not None:
            return denied
        try:
            return self._query(arguments, trusted)
        except CommerceValidationError as error:
            return ToolError.from_code(
                "INVALID_REQUEST", message_key=str(error),
                details_safe={"reason": str(error)},
            )
        except Exception as error:  # noqa: BLE001 - typed internal error
            return ToolError.from_code(
                "INTERNAL_ERROR", message_key="internal error",
                details_safe={"reason": str(error)},
            )

    # ── overridable hooks ────────────────────────────────────

    def _validate(self, arguments):
        pass

    def _check_scope(self, arguments, trusted):
        return None

    def _query(self, arguments, trusted):
        raise NotImplementedError

    def _context_key(self, arguments):
        return ""

    # ── pagination (shared cursor codec) ─────────────────────

    def _validate_pagination(self, arguments):
        if not self.paginated:
            return
        page = self._parse_page(arguments)
        validate_page(page)
        decode_cursor(page.cursor, self._context_key(arguments))

    # ── shared helpers ───────────────────────────────────────

    def _scope_deny(self, store_id):
        return ToolError.from_code(
            "PERMISSION_DENIED", message_key="store out of scope",
            details_safe={"store_id": store_id, "scope_policy": self.scope_policy},
        )

    def _require_store_scope(self, store_id, trusted):
        if store_id is None:
            return None
        if not store_in_scope(store_id, trusted):
            return self._scope_deny(store_id)
        return None

    @staticmethod
    def _parse_filters(arguments, allowed_fields):
        raw = arguments.get("filters") or []
        filters = []
        for item in raw:
            f = Filter(field=item["field"], operator=item["operator"],
                       value=item.get("value"))
            if f.field not in allowed_fields:
                raise CommerceValidationError(
                    f"filter field not allowed: {f.field!r}"
                )
            filters.append(f)
        return filters

    @staticmethod
    def _parse_page(arguments):
        raw = arguments.get("page") or {}
        return PageRequest(cursor=raw.get("cursor"), limit=raw.get("limit", 50))

    @staticmethod
    def _parse_time_range(arguments):
        raw = arguments.get("time_range") or {}
        return TimeRange(
            start=raw.get("start"), end=raw.get("end"),
            timezone=raw.get("timezone", "UTC"),
            boundary_policy=raw.get("boundary_policy", "INCLUSIVE"),
        )

    def _apply(self, items, filters, page, context_key):
        result = [item for item in items if all(_filter_match(item, f) for f in filters)]
        page_items, page_info = paginate(result, page, context_key)
        return page_items, page_info

    @staticmethod
    def _rebuild(result, data, page_info):
        return QueryResult(
            request_id=result.request_id or uuid.uuid4().hex,
            data=tuple(data),
            page=page_info,
            effective_scope=dict(result.effective_scope),
            freshness=result.freshness,
            quality=result.quality,
            provenance=result.provenance,
            warnings=tuple(result.warnings),
            partial=result.partial,
            executed_at=result.executed_at,
            duration_metadata=dict(result.duration_metadata),
        )


def _filter_match(item, f):
    value = getattr(item, f.field, None)
    if f.operator == "EQ":
        return value == f.value
    if f.operator == "IN":
        return value in (f.value or ())
    if f.operator == "GT":
        return value is not None and value > f.value
    if f.operator == "GTE":
        return value is not None and value >= f.value
    if f.operator == "LT":
        return value is not None and value < f.value
    if f.operator == "LTE":
        return value is not None and value <= f.value
    return True


# ── store.get (single record; no pagination) ────────────────

class StoreGetTool(CommerceReadTool):
    name = "store.get"
    capability = "commerce.store.read"
    description = "读取店铺身份与元数据"
    paginated = False

    def _validate(self, arguments):
        if not arguments.get("store_id") and not (
            arguments.get("platform") and arguments.get("external_store_id")
        ):
            raise CommerceValidationError(
                "store.get requires store_id or (platform, external_store_id)"
            )

    def _check_scope(self, arguments, trusted):
        if arguments.get("store_id"):
            return self._require_store_scope(arguments["store_id"], trusted)
        return None

    def _query(self, arguments, trusted):
        if arguments.get("store_id"):
            return self.query_service.get_store(trusted.tenant_id, arguments["store_id"])
        # External reference: resolve -> STRICT scope -> read business record.
        store_id = self.query_service.resolve_store_id_by_external(
            trusted.tenant_id, arguments["platform"], arguments["external_store_id"],
        )
        if store_id is None:
            return ToolError.from_code(
                "SUBJECT_NOT_FOUND", message_key="store not found",
                details_safe={"platform": arguments["platform"],
                              "external_store_id": arguments["external_store_id"]},
            )
        denied = self._require_store_scope(store_id, trusted)
        if denied is not None:
            return denied
        return self.query_service.get_store(trusted.tenant_id, store_id)


# ── catalog.query ───────────────────────────────────────────

class CatalogQueryTool(CommerceReadTool):
    name = "catalog.query"
    capability = "commerce.catalog.read"
    description = "读取商品/商品SKU/Listing/ListingItem"
    allowed_filter_fields = frozenset({"status", "brand", "category"})

    def _validate(self, arguments):
        subject_type = arguments.get("subject_type")
        if subject_type not in ("PRODUCT", "SKU", "LISTING", "LISTING_ITEM"):
            raise CommerceValidationError(
                f"unsupported catalog subject_type: {subject_type!r}"
            )
        self._parse_filters(arguments, self.allowed_filter_fields)

    def _check_scope(self, arguments, trusted):
        if arguments.get("subject_type") == "LISTING":
            return self._require_store_scope(arguments.get("store_id"), trusted)
        return None

    def _context_key(self, arguments):
        return (
            f"catalog:{arguments['subject_type']}:"
            f"{arguments.get('product_id') or arguments.get('store_id') or arguments.get('listing_id') or ''}"
        )

    def _query(self, arguments, trusted):
        subject_type = arguments["subject_type"]
        filters = self._parse_filters(arguments, self.allowed_filter_fields)
        page = self._parse_page(arguments)
        if subject_type == "PRODUCT":
            result = self.query_service.list_products(trusted.tenant_id)
        elif subject_type == "SKU":
            result = self.query_service.list_skus_by_product(
                trusted.tenant_id, arguments["product_id"]
            )
        elif subject_type == "LISTING":
            result = self.query_service.list_listings_by_store(
                trusted.tenant_id, arguments["store_id"]
            )
        else:
            result = self.query_service.list_listing_items_by_listing(
                trusted.tenant_id, arguments["listing_id"]
            )
        items, page_info = self._apply(result.data, filters, page, self._context_key(arguments))
        return self._rebuild(result, items, page_info)


# ── metric.query ────────────────────────────────────────────

class MetricQueryTool(CommerceReadTool):
    name = "metric.query"
    capability = "commerce.metrics.read"
    description = "读取 SOURCE/AGGREGATED 指标事实（禁止 DERIVED）"

    def __init__(self, query_service, metric_registry=None, allowed_filter_fields=None):
        super().__init__(query_service, allowed_filter_fields)
        self.metric_registry = metric_registry

    def _validate(self, arguments):
        if not arguments.get("subject_type") or not arguments.get("subject_id"):
            raise CommerceValidationError("metric.query requires subject_type + subject_id")
        for name in arguments.get("metric_names") or []:
            if self.metric_registry is not None:
                definition = self.metric_registry.get(name)
                if definition.metric_class == "DERIVED":
                    raise CommerceValidationError(
                        f"metric.query cannot serve DERIVED metric {name!r}"
                    )

    def _check_scope(self, arguments, trusted):
        if arguments.get("subject_type") == "STORE":
            return self._require_store_scope(arguments["subject_id"], trusted)
        return None

    def _context_key(self, arguments):
        return (
            f"metric:{arguments['subject_type']}:{arguments['subject_id']}:"
            f"{arguments.get('granularity') or ''}:"
            f"{','.join(sorted(arguments.get('metric_names') or []))}"
        )

    def _query(self, arguments, trusted):
        time_range = self._parse_time_range(arguments)
        result = self.query_service.query_metrics(
            trusted.tenant_id, arguments["subject_type"], arguments["subject_id"],
            metric_names=arguments.get("metric_names"),
            granularity=arguments.get("granularity"),
            time_range=time_range,
        )
        page = self._parse_page(arguments)
        items, page_info = self._apply(result.data, [], page, self._context_key(arguments))
        return self._rebuild(result, items, page_info)


# ── inventory.query ─────────────────────────────────────────

class InventoryQueryTool(CommerceReadTool):
    name = "inventory.query"
    capability = "commerce.inventory.read"
    description = "读取库存快照事实（禁止 DaysOfSupply/风险派生）"

    def _validate(self, arguments):
        if not arguments.get("store_id") or not arguments.get("sku_id"):
            raise CommerceValidationError(
                "inventory.query requires store_id + sku_id"
            )

    def _check_scope(self, arguments, trusted):
        return self._require_store_scope(arguments["store_id"], trusted)

    def _context_key(self, arguments):
        return f"inventory:{arguments['store_id']}:{arguments['sku_id']}"

    def _query(self, arguments, trusted):
        result = self.query_service.query_inventory(
            trusted.tenant_id, arguments["store_id"], arguments["sku_id"],
        )
        page = self._parse_page(arguments)
        items, page_info = self._apply(result.data, [], page, self._context_key(arguments))
        return self._rebuild(result, items, page_info)


# ── review.query ────────────────────────────────────────────

class ReviewQueryTool(CommerceReadTool):
    name = "review.query"
    capability = "commerce.review.read"
    description = "读取评价/评价洞察（默认不含原始评价内容）"

    def _validate(self, arguments):
        subject_type = arguments.get("subject_type", "REVIEW")
        if subject_type not in ("REVIEW", "REVIEW_INSIGHT"):
            raise CommerceValidationError(
                f"unsupported review subject_type: {subject_type!r}"
            )
        if subject_type == "REVIEW" and not arguments.get("listing_id"):
            raise CommerceValidationError("review.query REVIEW requires listing_id")
        if subject_type == "REVIEW_INSIGHT" and not arguments.get("review_id"):
            raise CommerceValidationError(
                "review.query REVIEW_INSIGHT requires review_id"
            )

    def _check_scope(self, arguments, trusted):
        return self._require_store_scope(arguments.get("store_id"), trusted)

    def _context_key(self, arguments):
        return (
            f"review:{arguments.get('subject_type', 'REVIEW')}:"
            f"{arguments.get('review_id') or arguments.get('listing_id') or ''}"
        )

    def _query(self, arguments, trusted):
        if arguments.get("subject_type") == "REVIEW_INSIGHT":
            result = self.query_service.list_review_insights_by_review(
                trusted.tenant_id, arguments["review_id"],
            )
            page = self._parse_page(arguments)
            items, page_info = self._apply(result.data, [], page, self._context_key(arguments))
            return self._rebuild(result, items, page_info)
        result = self.query_service.list_reviews_by_listing(
            trusted.tenant_id, arguments["listing_id"],
        )
        include_raw = arguments.get("include_raw", False)
        if not include_raw:
            data = []
            for review in result.data:
                item = review.to_dict()
                item.pop("content", None)
                item.pop("title", None)
                data.append(item)
            result = self._rebuild(result, data, result.page)
        page = self._parse_page(arguments)
        items, page_info = self._apply(result.data, [], page, self._context_key(arguments))
        return self._rebuild(result, items, page_info)


# ── review_insight.query ────────────────────────────────────

class ReviewInsightQueryTool(CommerceReadTool):
    name = "review_insight.query"
    capability = "commerce.review_insight.read"
    description = "读取评价洞察 AI 事实（issues/topics/confidence/severity + provenance）"

    def _validate(self, arguments):
        if not arguments.get("store_id"):
            raise CommerceValidationError("review_insight.query requires store_id")
        if not arguments.get("review_id") and not arguments.get("listing_id"):
            raise CommerceValidationError(
                "review_insight.query requires review_id or listing_id"
            )

    def _check_scope(self, arguments, trusted):
        return self._require_store_scope(arguments.get("store_id"), trusted)

    def _context_key(self, arguments):
        return (
            f"review_insight:"
            f"{arguments.get('review_id') or arguments.get('listing_id') or ''}"
        )

    def _query(self, arguments, trusted):
        if arguments.get("review_id"):
            result = self.query_service.list_review_insights_by_review(
                trusted.tenant_id, arguments["review_id"],
            )
        else:
            result = self.query_service.list_review_insights_by_listing(
                trusted.tenant_id, arguments["listing_id"],
            )
        page = self._parse_page(arguments)
        items, page_info = self._apply(result.data, [], page, self._context_key(arguments))
        return self._rebuild(result, items, page_info)


# ── advertising.query ───────────────────────────────────────

class AdvertisingQueryTool(CommerceReadTool):
    name = "advertising.query"
    capability = "commerce.advertising.read"
    description = "读取广告实体（Campaign/AdGroup/Ad/Keyword/SearchTerm），不返回派生指标"

    def _validate(self, arguments):
        subject_type = arguments.get("subject_type")
        if subject_type not in (
            "CAMPAIGN", "AD_GROUP", "AD", "AD_PROMOTED_ITEM", "KEYWORD", "SEARCH_TERM",
        ):
            raise CommerceValidationError(
                f"unsupported advertising subject_type: {subject_type!r}"
            )

    def _check_scope(self, arguments, trusted):
        return self._require_store_scope(arguments.get("store_id"), trusted)

    def _context_key(self, arguments):
        return (
            f"advertising:{arguments['subject_type']}:"
            f"{arguments.get('store_id') or arguments.get('campaign_id') or arguments.get('ad_group_id') or arguments.get('ad_id') or ''}"
        )

    def _query(self, arguments, trusted):
        subject_type = arguments["subject_type"]
        if subject_type == "CAMPAIGN":
            result = self.query_service.list_campaigns_by_store(
                trusted.tenant_id, arguments["store_id"],
            )
        elif subject_type == "AD_GROUP":
            result = self.query_service.list_ad_groups_by_campaign(
                trusted.tenant_id, arguments["campaign_id"],
            )
        elif subject_type == "AD":
            result = self.query_service.list_ads_by_ad_group(
                trusted.tenant_id, arguments["ad_group_id"],
            )
        elif subject_type == "KEYWORD":
            result = self.query_service.list_keywords_by_ad_group(
                trusted.tenant_id, arguments["ad_group_id"],
            )
        elif subject_type == "SEARCH_TERM":
            result = self.query_service.list_search_terms_by_ad_group(
                trusted.tenant_id, arguments["ad_group_id"],
            )
        else:
            result = self.query_service.list_promoted_items_by_ad(
                trusted.tenant_id, arguments["ad_id"],
            )
        page = self._parse_page(arguments)
        items, page_info = self._apply(result.data, [], page, self._context_key(arguments))
        return self._rebuild(result, items, page_info)


def build_commerce_tools(query_service, metric_registry=None):
    return {
        "store.get": StoreGetTool(query_service),
        "catalog.query": CatalogQueryTool(query_service),
        "metric.query": MetricQueryTool(query_service, metric_registry=metric_registry),
        "inventory.query": InventoryQueryTool(query_service),
        "review.query": ReviewQueryTool(query_service),
        "review_insight.query": ReviewInsightQueryTool(query_service),
        "advertising.query": AdvertisingQueryTool(query_service),
    }


__all__ = [
    "CommerceReadTool",
    "StoreGetTool",
    "CatalogQueryTool",
    "MetricQueryTool",
    "InventoryQueryTool",
    "ReviewQueryTool",
    "ReviewInsightQueryTool",
    "AdvertisingQueryTool",
    "build_commerce_tools",
]
