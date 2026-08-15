"""Transaction domain: Order, OrderItem.

v1 establishes the canonical transaction model, but raw Order detail is not a
first-stage Read Tool.  Store / SKU operational diagnosis reads aggregated facts
via ``MetricSeries`` first; Order/OrderItem exist for downstream reconciliation.
"""

from dataclasses import dataclass, field

from app.commerce.domain.base import utc_now


@dataclass(frozen=True)
class Order:
    order_id: str
    tenant_id: str
    store_id: str
    external_order_id: str
    status: str = "pending"
    currency: str = ""
    gross_amount: float = 0.0
    discount_amount: float = 0.0
    refund_amount: float = 0.0
    net_amount: float = 0.0
    ordered_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "external_order_id": self.external_order_id,
            "status": self.status,
            "currency": self.currency,
            "gross_amount": self.gross_amount,
            "discount_amount": self.discount_amount,
            "refund_amount": self.refund_amount,
            "net_amount": self.net_amount,
            "ordered_at": self.ordered_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Order":
        return cls(
            order_id=data["order_id"],
            tenant_id=data["tenant_id"],
            store_id=data["store_id"],
            external_order_id=data["external_order_id"],
            status=data.get("status", "pending"),
            currency=data.get("currency", ""),
            gross_amount=data.get("gross_amount", 0.0),
            discount_amount=data.get("discount_amount", 0.0),
            refund_amount=data.get("refund_amount", 0.0),
            net_amount=data.get("net_amount", 0.0),
            ordered_at=data.get("ordered_at"),
        )


@dataclass(frozen=True)
class OrderItem:
    order_item_id: str
    order_id: str
    sku_id: str
    listing_item_id: str | None = None
    quantity: int = 1
    unit_price: float = 0.0
    discount_amount: float = 0.0
    net_amount: float = 0.0

    def to_dict(self) -> dict:
        return {
            "order_item_id": self.order_item_id,
            "order_id": self.order_id,
            "sku_id": self.sku_id,
            "listing_item_id": self.listing_item_id,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "discount_amount": self.discount_amount,
            "net_amount": self.net_amount,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OrderItem":
        return cls(
            order_item_id=data["order_item_id"],
            order_id=data["order_id"],
            sku_id=data["sku_id"],
            listing_item_id=data.get("listing_item_id"),
            quantity=data.get("quantity", 1),
            unit_price=data.get("unit_price", 0.0),
            discount_amount=data.get("discount_amount", 0.0),
            net_amount=data.get("net_amount", 0.0),
        )


__all__ = ["Order", "OrderItem"]
