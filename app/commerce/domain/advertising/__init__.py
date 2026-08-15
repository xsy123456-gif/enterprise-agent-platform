"""Advertising domain.

Canonical advertising is platform-neutral and must not mirror an Amazon
private model.  Hierarchy::

    Store -> Campaign -> AdGroup -> Ad -> AdPromotedItem
                     AdGroup -> Keyword
                     AdGroup -> SearchTerm

``Ad`` never stores ``sku_id`` / ``listing_id``; the promoted item link is the
separate ``AdPromotedItem`` entity (one Ad may promote many items).  Keyword
and SearchTerm are distinct entities.
"""

from dataclasses import dataclass, field
from typing import Any

from app.commerce.domain.base import utc_now


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    tenant_id: str
    store_id: str
    platform: str
    external_campaign_id: str
    name: str
    campaign_type: str = "OTHER"
    objective: str = "OTHER"
    status: str = "active"
    budget_type: str = ""
    daily_budget: float | None = None
    currency: str = ""
    start_at: str | None = None
    end_at: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return {
            "campaign_id": self.campaign_id,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "platform": self.platform,
            "external_campaign_id": self.external_campaign_id,
            "name": self.name,
            "campaign_type": self.campaign_type,
            "objective": self.objective,
            "status": self.status,
            "budget_type": self.budget_type,
            "daily_budget": self.daily_budget,
            "currency": self.currency,
            "start_at": self.start_at,
            "end_at": self.end_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Campaign":
        return cls(
            campaign_id=data["campaign_id"],
            tenant_id=data["tenant_id"],
            store_id=data["store_id"],
            platform=data["platform"],
            external_campaign_id=data["external_campaign_id"],
            name=data["name"],
            campaign_type=data.get("campaign_type", "OTHER"),
            objective=data.get("objective", "OTHER"),
            status=data.get("status", "active"),
            budget_type=data.get("budget_type", ""),
            daily_budget=data.get("daily_budget"),
            currency=data.get("currency", ""),
            start_at=data.get("start_at"),
            end_at=data.get("end_at"),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )


@dataclass(frozen=True)
class AdGroup:
    ad_group_id: str
    campaign_id: str
    external_ad_group_id: str
    name: str
    status: str = "active"
    default_bid: float | None = None
    targeting_type: str = "OTHER"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return {
            "ad_group_id": self.ad_group_id,
            "campaign_id": self.campaign_id,
            "external_ad_group_id": self.external_ad_group_id,
            "name": self.name,
            "status": self.status,
            "default_bid": self.default_bid,
            "targeting_type": self.targeting_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AdGroup":
        return cls(
            ad_group_id=data["ad_group_id"],
            campaign_id=data["campaign_id"],
            external_ad_group_id=data["external_ad_group_id"],
            name=data["name"],
            status=data.get("status", "active"),
            default_bid=data.get("default_bid"),
            targeting_type=data.get("targeting_type", "OTHER"),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )


@dataclass(frozen=True)
class Ad:
    ad_id: str
    ad_group_id: str
    external_ad_id: str
    ad_type: str = "OTHER"
    creative_ref: str | None = None
    status: str = "active"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return {
            "ad_id": self.ad_id,
            "ad_group_id": self.ad_group_id,
            "external_ad_id": self.external_ad_id,
            "ad_type": self.ad_type,
            "creative_ref": self.creative_ref,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Ad":
        return cls(
            ad_id=data["ad_id"],
            ad_group_id=data["ad_group_id"],
            external_ad_id=data["external_ad_id"],
            ad_type=data.get("ad_type", "OTHER"),
            creative_ref=data.get("creative_ref"),
            status=data.get("status", "active"),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )


@dataclass(frozen=True)
class AdPromotedItem:
    ad_promoted_item_id: str
    ad_id: str
    listing_id: str
    listing_item_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "ad_promoted_item_id": self.ad_promoted_item_id,
            "ad_id": self.ad_id,
            "listing_id": self.listing_id,
            "listing_item_id": self.listing_item_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AdPromotedItem":
        return cls(
            ad_promoted_item_id=data["ad_promoted_item_id"],
            ad_id=data["ad_id"],
            listing_id=data["listing_id"],
            listing_item_id=data.get("listing_item_id"),
        )


@dataclass(frozen=True)
class Keyword:
    keyword_id: str
    ad_group_id: str
    external_keyword_id: str
    keyword_text: str
    match_type: str = "OTHER"
    bid: float | None = None
    status: str = "active"
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return {
            "keyword_id": self.keyword_id,
            "ad_group_id": self.ad_group_id,
            "external_keyword_id": self.external_keyword_id,
            "keyword_text": self.keyword_text,
            "match_type": self.match_type,
            "bid": self.bid,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Keyword":
        return cls(
            keyword_id=data["keyword_id"],
            ad_group_id=data["ad_group_id"],
            external_keyword_id=data["external_keyword_id"],
            keyword_text=data["keyword_text"],
            match_type=data.get("match_type", "OTHER"),
            bid=data.get("bid"),
            status=data.get("status", "active"),
            created_at=data.get("created_at", utc_now()),
        )


@dataclass(frozen=True)
class SearchTerm:
    search_term_id: str
    ad_group_id: str
    search_term: str
    keyword_id: str | None = None
    observed_date: str | None = None
    dimensions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "dimensions", dict(self.dimensions or {}))

    def to_dict(self) -> dict:
        return {
            "search_term_id": self.search_term_id,
            "ad_group_id": self.ad_group_id,
            "keyword_id": self.keyword_id,
            "search_term": self.search_term,
            "observed_date": self.observed_date,
            "dimensions": dict(self.dimensions),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SearchTerm":
        return cls(
            search_term_id=data["search_term_id"],
            ad_group_id=data["ad_group_id"],
            search_term=data["search_term"],
            keyword_id=data.get("keyword_id"),
            observed_date=data.get("observed_date"),
            dimensions=data.get("dimensions", {}),
        )


__all__ = [
    "Campaign",
    "AdGroup",
    "Ad",
    "AdPromotedItem",
    "Keyword",
    "SearchTerm",
]
