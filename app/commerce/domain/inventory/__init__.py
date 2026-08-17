"""Inventory domain: InventorySnapshot.

Inventory is *time-state*, not a mutable SKU field.  ``InventorySnapshot`` is
appended per observation; the query layer resolves "current inventory" from the
most recent valid snapshot for a given (store, sku, source).
"""

from dataclasses import dataclass, field
from typing import Any

from app.commerce.domain.base import utc_now


@dataclass(frozen=True)
class InventorySnapshot:
    inventory_snapshot_id: str
    tenant_id: str
    store_id: str
    sku_id: str
    on_hand_quantity: int = 0
    available_quantity: int = 0
    reserved_quantity: int = 0
    inbound_quantity: int = 0
    snapshot_at: str = field(default_factory=utc_now)
    source_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "source_metadata", dict(self.source_metadata or {}))

    def to_dict(self) -> dict:
        return {
            "inventory_snapshot_id": self.inventory_snapshot_id,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "sku_id": self.sku_id,
            "on_hand_quantity": self.on_hand_quantity,
            "available_quantity": self.available_quantity,
            "reserved_quantity": self.reserved_quantity,
            "inbound_quantity": self.inbound_quantity,
            "snapshot_at": self.snapshot_at,
            "source_metadata": dict(self.source_metadata),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InventorySnapshot":
        return cls(
            inventory_snapshot_id=data["inventory_snapshot_id"],
            tenant_id=data["tenant_id"],
            store_id=data["store_id"],
            sku_id=data["sku_id"],
            on_hand_quantity=data.get("on_hand_quantity", 0),
            available_quantity=data.get("available_quantity", 0),
            reserved_quantity=data.get("reserved_quantity", 0),
            inbound_quantity=data.get("inbound_quantity", 0),
            snapshot_at=data.get("snapshot_at", utc_now()),
            source_metadata=data.get("source_metadata", {}),
        )


__all__ = ["InventorySnapshot"]
