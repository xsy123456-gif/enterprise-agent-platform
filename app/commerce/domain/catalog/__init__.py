"""Catalog domain: Store, Product, SKU, Listing, ListingItem.

Relationship invariants (frozen for v1):

- ``Listing 1:N ListingItem`` (a Listing has many sellable variants).
- ``SKU 1:N ListingItem`` (a SKU may appear in many Listings).
- ``Listing`` never stores ``sku_id`` directly; that would collapse the 1:N
  relationship into 1:1.
"""

from dataclasses import dataclass, field
from typing import Any

from app.commerce.domain.base import utc_now


@dataclass(frozen=True)
class Store:
    store_id: str
    tenant_id: str
    platform: str
    marketplace: str
    external_store_id: str
    name: str
    currency: str
    timezone: str
    status: str = "active"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return {
            "store_id": self.store_id,
            "tenant_id": self.tenant_id,
            "platform": self.platform,
            "marketplace": self.marketplace,
            "external_store_id": self.external_store_id,
            "name": self.name,
            "currency": self.currency,
            "timezone": self.timezone,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Store":
        return cls(
            store_id=data["store_id"],
            tenant_id=data["tenant_id"],
            platform=data["platform"],
            marketplace=data["marketplace"],
            external_store_id=data["external_store_id"],
            name=data["name"],
            currency=data["currency"],
            timezone=data["timezone"],
            status=data.get("status", "active"),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )


@dataclass(frozen=True)
class Product:
    product_id: str
    tenant_id: str
    title: str
    brand: str = ""
    category: str = ""
    product_type: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "active"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        object.__setattr__(self, "attributes", dict(self.attributes or {}))

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "tenant_id": self.tenant_id,
            "title": self.title,
            "brand": self.brand,
            "category": self.category,
            "product_type": self.product_type,
            "attributes": dict(self.attributes),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        return cls(
            product_id=data["product_id"],
            tenant_id=data["tenant_id"],
            title=data["title"],
            brand=data.get("brand", ""),
            category=data.get("category", ""),
            product_type=data.get("product_type", ""),
            attributes=data.get("attributes", {}),
            status=data.get("status", "active"),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )


@dataclass(frozen=True)
class SKU:
    sku_id: str
    tenant_id: str
    product_id: str
    merchant_sku: str
    variant_attributes: dict[str, Any] = field(default_factory=dict)
    cost: float | None = None
    status: str = "active"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        object.__setattr__(self, "variant_attributes", dict(self.variant_attributes or {}))

    def to_dict(self) -> dict:
        return {
            "sku_id": self.sku_id,
            "tenant_id": self.tenant_id,
            "product_id": self.product_id,
            "merchant_sku": self.merchant_sku,
            "variant_attributes": dict(self.variant_attributes),
            "cost": self.cost,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SKU":
        return cls(
            sku_id=data["sku_id"],
            tenant_id=data["tenant_id"],
            product_id=data["product_id"],
            merchant_sku=data["merchant_sku"],
            variant_attributes=data.get("variant_attributes", {}),
            cost=data.get("cost"),
            status=data.get("status", "active"),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )


@dataclass(frozen=True)
class Listing:
    listing_id: str
    tenant_id: str
    store_id: str
    platform: str
    external_listing_id: str
    title: str = ""
    parent_external_id: str | None = None
    status: str = "active"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return {
            "listing_id": self.listing_id,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "platform": self.platform,
            "external_listing_id": self.external_listing_id,
            "title": self.title,
            "parent_external_id": self.parent_external_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Listing":
        return cls(
            listing_id=data["listing_id"],
            tenant_id=data["tenant_id"],
            store_id=data["store_id"],
            platform=data["platform"],
            external_listing_id=data["external_listing_id"],
            title=data.get("title", ""),
            parent_external_id=data.get("parent_external_id"),
            status=data.get("status", "active"),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )


@dataclass(frozen=True)
class ListingItem:
    listing_item_id: str
    listing_id: str
    sku_id: str
    external_sku_id: str
    variant_attributes: dict[str, Any] = field(default_factory=dict)
    price: float | None = None
    status: str = "active"
    updated_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        object.__setattr__(self, "variant_attributes", dict(self.variant_attributes or {}))

    def to_dict(self) -> dict:
        return {
            "listing_item_id": self.listing_item_id,
            "listing_id": self.listing_id,
            "sku_id": self.sku_id,
            "external_sku_id": self.external_sku_id,
            "variant_attributes": dict(self.variant_attributes),
            "price": self.price,
            "status": self.status,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ListingItem":
        return cls(
            listing_item_id=data["listing_item_id"],
            listing_id=data["listing_id"],
            sku_id=data["sku_id"],
            external_sku_id=data["external_sku_id"],
            variant_attributes=data.get("variant_attributes", {}),
            price=data.get("price"),
            status=data.get("status", "active"),
            updated_at=data.get("updated_at", utc_now()),
        )


__all__ = ["Store", "Product", "SKU", "Listing", "ListingItem"]
