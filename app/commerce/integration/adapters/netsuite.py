"""NetSuite adapter — Phase 18.13.4.

Maps NetSuite ERP DTOs into canonical mutations (item -> Product, inventory ->
InventorySnapshot append, sales order -> Order).  ERP-only mapping.
"""

from app.commerce.ingestion.ports import AdapterMappingError
from app.commerce.integration.adapters.base import (
    BaseAdapter,
    MUTATION_APPEND,
    MUTATION_UPSERT,
)


class NetSuiteAdapter(BaseAdapter):
    adapter_id = "netsuite_adapter"

    def adapt(self, envelope):
        payload = envelope.payload
        resource = (envelope.resource or payload.get("resource") or "").upper()
        if resource == "ITEM":
            return self._item(payload, envelope)
        if resource == "INVENTORY":
            return self._inventory(payload, envelope)
        if resource == "SALES_ORDER":
            return self._sales_order(payload, envelope)
        raise AdapterMappingError(
            f"netsuite adapter does not support resource {resource!r}"
        )

    def _item(self, payload, envelope):
        item_id = payload.get("itemId") or payload.get("external_id")
        if not item_id:
            raise AdapterMappingError("netsuite item is missing itemId")
        product_id = f"product_{item_id}"
        entity = {
            "product_id": product_id,
            "tenant_id": self.tenant_id,
            "title": payload.get("displayName", ""),
            "product_type": payload.get("type", ""),
        }
        return [self._mutation(MUTATION_UPSERT, "product", entity, envelope,
                               external_id=item_id, resource_type="product",
                               canonical_id=product_id)]

    def _inventory(self, payload, envelope):
        item_id = payload.get("itemId") or payload.get("external_id")
        if not item_id:
            raise AdapterMappingError("netsuite inventory is missing itemId")
        entity = {
            "inventory_snapshot_id": f"inv_{envelope.source_record_id}",
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "sku_id": item_id,
            "available_quantity": payload.get("available", payload.get("onHand", 0)),
            "snapshot_at": envelope.source_observed_at or "",
        }
        return [self._mutation(MUTATION_APPEND, "inventory_snapshot", entity,
                               envelope, external_id=item_id,
                               resource_type="inventory_snapshot",
                               canonical_id=entity["inventory_snapshot_id"])]

    def _sales_order(self, payload, envelope):
        internal_id = payload.get("internalId") or payload.get("external_id")
        if not internal_id:
            raise AdapterMappingError("netsuite sales order is missing internalId")
        canonical_id = f"order_{internal_id}"
        entity = {
            "order_id": canonical_id,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "external_order_id": internal_id,
            "status": str(payload.get("status", "pending")).lower(),
            "gross_amount": payload.get("amount", 0.0),
        }
        return [self._mutation(MUTATION_UPSERT, "order", entity, envelope,
                               external_id=internal_id, resource_type="order",
                               canonical_id=canonical_id)]


__all__ = ["NetSuiteAdapter"]
