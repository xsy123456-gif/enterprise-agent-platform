"""SAP adapter — Phase 18.13.4.

Maps SAP ERP DTOs into canonical mutations (MATNR material master -> Product,
inventory LABST -> InventorySnapshot append).  ERP-only mapping; it never
produces advertising / review entities and never computes metrics.
"""

from app.commerce.ingestion.ports import AdapterMappingError
from app.commerce.integration.adapters.base import (
    BaseAdapter,
    MUTATION_APPEND,
    MUTATION_UPSERT,
)


class SapAdapter(BaseAdapter):
    adapter_id = "sap_adapter"

    def adapt(self, envelope):
        payload = envelope.payload
        resource = (envelope.resource or payload.get("resource") or "").upper()
        if resource == "MATERIAL":
            return self._material(payload, envelope)
        if resource == "INVENTORY":
            return self._inventory(payload, envelope)
        raise AdapterMappingError(
            f"sap adapter does not support resource {resource!r}"
        )

    def _material(self, payload, envelope):
        matnr = payload.get("MATNR") or payload.get("external_id")
        if not matnr:
            raise AdapterMappingError("sap material is missing MATNR")
        product_id = f"product_{matnr}"
        entity = {
            "product_id": product_id,
            "tenant_id": self.tenant_id,
            "title": payload.get("MAKTX", ""),
            "product_type": payload.get("MTART", ""),
        }
        return [self._mutation(MUTATION_UPSERT, "product", entity, envelope,
                               external_id=matnr, resource_type="product",
                               canonical_id=product_id)]

    def _inventory(self, payload, envelope):
        matnr = payload.get("MATNR") or payload.get("external_id")
        if not matnr:
            raise AdapterMappingError("sap inventory is missing MATNR")
        entity = {
            "inventory_snapshot_id": f"inv_{envelope.source_record_id}",
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "sku_id": matnr,
            "available_quantity": payload.get("LABST", 0),
            "snapshot_at": payload.get("ERSDA") or "",
        }
        return [self._mutation(MUTATION_APPEND, "inventory_snapshot", entity,
                               envelope, external_id=matnr,
                               resource_type="inventory_snapshot",
                               canonical_id=entity["inventory_snapshot_id"])]


__all__ = ["SapAdapter"]
