"""TikTok adapter — Phase 12.9.5.

Maps TikTok Shop DTOs into canonical ``CanonicalMutation`` (Product ID ->
Listing, Inventory -> append, Review -> Review).  Mapping only — no metrics, no
anomalies, no Cause / Impact.
"""

from app.commerce.ingestion.ports import AdapterMappingError
from app.commerce.integration.adapters.base import (
    BaseAdapter,
    MUTATION_APPEND,
    MUTATION_UPSERT,
)


class TikTokAdapter(BaseAdapter):
    adapter_id = "tiktok_adapter"

    def adapt(self, envelope):
        payload = envelope.payload
        resource = (payload.get("resource") or "").upper()
        if resource == "PRODUCT":
            return self._product(payload, envelope)
        if resource == "INVENTORY":
            return self._inventory(payload, envelope)
        if resource == "REVIEW":
            return self._review(payload, envelope)
        raise AdapterMappingError(
            f"tiktok adapter does not support resource {resource!r}"
        )

    def _product(self, payload, envelope):
        product_id = payload.get("product_id") or payload.get("external_id")
        if not product_id:
            raise AdapterMappingError("tiktok product is missing product_id")
        listing_id = f"listing_{product_id}"
        entity = {
            "listing_id": listing_id,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "platform": "tiktok",
            "external_listing_id": product_id,
            "title": payload.get("title", ""),
        }
        return [self._mutation(MUTATION_UPSERT, "listing", entity, envelope,
                               external_id=product_id, resource_type="listing",
                               canonical_id=listing_id)]

    def _inventory(self, payload, envelope):
        sku = payload.get("sku") or payload.get("external_id")
        if not sku:
            raise AdapterMappingError("tiktok inventory is missing sku")
        entity = {
            "inventory_snapshot_id": f"inv_{envelope.source_record_id}",
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "sku_id": sku,
            "available_quantity": payload.get("stock", 0),
            "snapshot_at": envelope.source_observed_at or "",
        }
        return [self._mutation(MUTATION_APPEND, "inventory_snapshot", entity,
                               envelope, external_id=sku,
                               resource_type="inventory_snapshot",
                               canonical_id=entity["inventory_snapshot_id"])]

    def _review(self, payload, envelope):
        external_review_id = payload.get("review_id") or payload.get("external_id")
        if not external_review_id:
            raise AdapterMappingError("tiktok review is missing review_id")
        review_id = f"review_{external_review_id}"
        entity = {
            "review_id": review_id,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "listing_id": payload.get("listing_id", ""),
            "platform": "tiktok",
            "external_review_id": external_review_id,
            "rating": payload.get("rating", 0.0),
            "content": payload.get("content", ""),
        }
        return [self._mutation(MUTATION_UPSERT, "review", entity, envelope,
                               external_id=external_review_id,
                               resource_type="review", canonical_id=review_id)]


__all__ = ["TikTokAdapter"]
