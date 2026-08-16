"""Amazon adapter — Phase 12.9.4.

Maps Amazon Seller DTOs into canonical ``CanonicalMutation`` (ASIN -> Listing,
FBA inventory -> InventorySnapshot append, Review DTO -> Review).  It only does
field/enum/identity mapping — never computes metrics, never detects anomalies,
never creates Cause / Impact.
"""

from app.commerce.ingestion.ports import AdapterMappingError
from app.commerce.integration.adapters.base import (
    BaseAdapter,
    MUTATION_APPEND,
    MUTATION_UPSERT,
)


class AmazonAdapter(BaseAdapter):
    adapter_id = "amazon_adapter"

    def adapt(self, envelope):
        payload = envelope.payload
        resource = (payload.get("resource") or "").upper()
        if resource == "LISTING":
            return self._listing(payload, envelope)
        if resource == "INVENTORY":
            return self._inventory(payload, envelope)
        if resource == "REVIEW":
            return self._review(payload, envelope)
        raise AdapterMappingError(
            f"amazon adapter does not support resource {resource!r}"
        )

    def _listing(self, payload, envelope):
        asin = payload.get("asin") or payload.get("external_id")
        if not asin:
            raise AdapterMappingError("amazon listing is missing asin")
        listing_id = f"listing_{asin}"
        entity = {
            "listing_id": listing_id,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "platform": "amazon",
            "external_listing_id": asin,
            "title": payload.get("title", ""),
        }
        return [self._mutation(MUTATION_UPSERT, "listing", entity, envelope,
                               external_id=asin, resource_type="listing",
                               canonical_id=listing_id)]

    def _inventory(self, payload, envelope):
        sku = payload.get("sku") or payload.get("external_id")
        if not sku:
            raise AdapterMappingError("amazon inventory is missing sku")
        entity = {
            "inventory_snapshot_id": f"inv_{envelope.source_record_id}",
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "sku_id": sku,
            "available_quantity": payload.get("quantity", 0),
            "snapshot_at": envelope.source_observed_at or "",
        }
        return [self._mutation(MUTATION_APPEND, "inventory_snapshot", entity,
                               envelope, external_id=sku,
                               resource_type="inventory_snapshot",
                               canonical_id=entity["inventory_snapshot_id"])]

    def _review(self, payload, envelope):
        external_review_id = payload.get("review_id") or payload.get("external_id")
        if not external_review_id:
            raise AdapterMappingError("amazon review is missing review_id")
        review_id = f"review_{external_review_id}"
        entity = {
            "review_id": review_id,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "listing_id": payload.get("listing_id", ""),
            "platform": "amazon",
            "external_review_id": external_review_id,
            "rating": payload.get("rating", 0.0),
            "content": payload.get("content", ""),
        }
        return [self._mutation(MUTATION_UPSERT, "review", entity, envelope,
                               external_id=external_review_id,
                               resource_type="review", canonical_id=review_id)]


__all__ = ["AmazonAdapter"]
