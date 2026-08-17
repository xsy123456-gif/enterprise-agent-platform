"""Amazon adapter — Phase 12.9.4 / 18.13.4.

Maps Amazon Seller DTOs into canonical mutations (ASIN -> Listing, orderId ->
Order, inventory -> InventorySnapshot append, campaignId -> Campaign, review ->
Review).  It only does field/enum/identity mapping — never computes metrics,
never detects anomalies, never creates Cause / Impact.
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
        resource = (envelope.resource or payload.get("resource") or "").upper()
        if resource == "LISTING":
            return self._listing(payload, envelope)
        if resource == "ORDER":
            return self._order(payload, envelope)
        if resource == "INVENTORY":
            return self._inventory(payload, envelope)
        if resource == "CAMPAIGN":
            return self._campaign(payload, envelope)
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
            "title": payload.get("itemName", payload.get("title", "")),
        }
        return [self._mutation(MUTATION_UPSERT, "listing", entity, envelope,
                               external_id=asin, resource_type="listing",
                               canonical_id=listing_id)]

    def _order(self, payload, envelope):
        order_id = payload.get("orderId") or payload.get("external_id")
        if not order_id:
            raise AdapterMappingError("amazon order is missing orderId")
        canonical_id = f"order_{order_id}"
        entity = {
            "order_id": canonical_id,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "external_order_id": order_id,
            "status": str(payload.get("orderStatus", "pending")).lower(),
            "currency": payload.get("currency", ""),
            "gross_amount": payload.get("amount", 0.0),
            "ordered_at": payload.get("purchaseDate") or "",
        }
        return [self._mutation(MUTATION_UPSERT, "order", entity, envelope,
                               external_id=order_id, resource_type="order",
                               canonical_id=canonical_id)]

    def _inventory(self, payload, envelope):
        sku = payload.get("sku") or payload.get("external_id")
        if not sku:
            raise AdapterMappingError("amazon inventory is missing sku")
        entity = {
            "inventory_snapshot_id": f"inv_{envelope.source_record_id}",
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "sku_id": sku,
            "available_quantity": payload.get("fulfillable", payload.get("quantity", 0)),
            "snapshot_at": envelope.source_observed_at or "",
        }
        return [self._mutation(MUTATION_APPEND, "inventory_snapshot", entity,
                               envelope, external_id=sku,
                               resource_type="inventory_snapshot",
                               canonical_id=entity["inventory_snapshot_id"])]

    def _campaign(self, payload, envelope):
        campaign_id = payload.get("campaignId") or payload.get("external_id")
        if not campaign_id:
            raise AdapterMappingError("amazon campaign is missing campaignId")
        canonical_id = f"campaign_{campaign_id}"
        entity = {
            "campaign_id": canonical_id,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "platform": "amazon",
            "external_campaign_id": campaign_id,
            "name": payload.get("name", ""),
            "status": str(payload.get("state", "active")).lower(),
            "daily_budget": payload.get("dailyBudget"),
        }
        return [self._mutation(MUTATION_UPSERT, "campaign", entity, envelope,
                               external_id=campaign_id, resource_type="campaign",
                               canonical_id=canonical_id)]

    def _review(self, payload, envelope):
        external_review_id = payload.get("reviewId") or payload.get("external_id")
        if not external_review_id:
            raise AdapterMappingError("amazon review is missing reviewId")
        review_id = f"review_{external_review_id}"
        entity = {
            "review_id": review_id,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "listing_id": payload.get("asin", ""),
            "platform": "amazon",
            "external_review_id": external_review_id,
            "rating": payload.get("rating", 0.0),
            "title": payload.get("title", ""),
            "content": payload.get("content", ""),
        }
        return [self._mutation(MUTATION_UPSERT, "review", entity, envelope,
                               external_id=external_review_id,
                               resource_type="review", canonical_id=review_id)]


__all__ = ["AmazonAdapter"]
