"""Canonical Commerce Model.

Platform-neutral domain entities.  Amazon / TikTok / Shopify data must be
mapped through a Connector + Adapter into these canonical records before any
Skill, DiagnosticPlan, Kernel Engine or Read Tool may touch them.  No
platform-specific DTO may leak into this package.
"""

from app.commerce.domain.advertising import (
    Ad,
    AdGroup,
    AdPromotedItem,
    Campaign,
    Keyword,
    SearchTerm,
)
from app.commerce.domain.base import ExternalIdentity
from app.commerce.domain.catalog import Listing, ListingItem, Product, SKU, Store
from app.commerce.domain.inventory import InventorySnapshot
from app.commerce.domain.metrics import (
    METRIC_CLASS_AGGREGATED,
    METRIC_CLASS_DERIVED,
    METRIC_CLASS_SOURCE,
    METRIC_CLASSES,
    MetricDefinition,
    MetricSeries,
)
from app.commerce.domain.operations import OperationalIssue
from app.commerce.domain.review import Review, ReviewInsight
from app.commerce.domain.transaction import Order, OrderItem

__all__ = [
    "ExternalIdentity",
    "Store",
    "Product",
    "SKU",
    "Listing",
    "ListingItem",
    "Order",
    "OrderItem",
    "InventorySnapshot",
    "Campaign",
    "AdGroup",
    "Ad",
    "AdPromotedItem",
    "Keyword",
    "SearchTerm",
    "Review",
    "ReviewInsight",
    "MetricSeries",
    "MetricDefinition",
    "METRIC_CLASS_SOURCE",
    "METRIC_CLASS_AGGREGATED",
    "METRIC_CLASS_DERIVED",
    "METRIC_CLASSES",
    "OperationalIssue",
]
