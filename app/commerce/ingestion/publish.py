"""Canonical Staging + validation and the Publish Manager.

Staging validates + referentially-checks mutations before publish; the
PublishManager applies valid mutations idempotently (at-least-once) to the
Canonical Repository and the ExternalIdentityMap.  Tombstones are only applied
for a COMPLETE full snapshot.  The committed watermark is advanced by the
Coordinator only after a fully successful publish (Last Known Good).
"""

from app.commerce.domain import (
    Ad,
    AdGroup,
    AdPromotedItem,
    Campaign,
    InventorySnapshot,
    Keyword,
    Listing,
    ListingItem,
    MetricSeries,
    Product,
    Review,
    ReviewInsight,
    SKU,
    SearchTerm,
    Store,
)
from app.commerce.ingestion.envelope import (
    MUTATION_APPEND,
    MUTATION_TOMBSTONE,
    MUTATION_UPSERT,
)

_RESOURCE_CLASSES = {
    "store": Store,
    "product": Product,
    "sku": SKU,
    "listing": Listing,
    "listing_item": ListingItem,
    "inventory_snapshot": InventorySnapshot,
    "campaign": Campaign,
    "ad_group": AdGroup,
    "ad": Ad,
    "ad_promoted_item": AdPromotedItem,
    "keyword": Keyword,
    "search_term": SearchTerm,
    "review": Review,
    "review_insight": ReviewInsight,
    "metric": MetricSeries,
}

_RESOURCE_METHODS = {
    "store": "upsert_store",
    "product": "upsert_product",
    "sku": "upsert_sku",
    "listing": "upsert_listing",
    "listing_item": "upsert_listing_item",
    "inventory_snapshot": "append_inventory_snapshot",
    "campaign": "upsert_campaign",
    "ad_group": "upsert_ad_group",
    "ad": "upsert_ad",
    "ad_promoted_item": "upsert_ad_promoted_item",
    "keyword": "upsert_keyword",
    "search_term": "upsert_search_term",
    "review": "upsert_review",
    "review_insight": "upsert_review_insight",
    "metric": "upsert_metric",
}

_RESOURCE_ID_FIELDS = {
    "store": "store_id",
    "product": "product_id",
    "sku": "sku_id",
    "listing": "listing_id",
    "listing_item": "listing_item_id",
    "inventory_snapshot": "inventory_snapshot_id",
    "campaign": "campaign_id",
    "ad_group": "ad_group_id",
    "ad": "ad_id",
    "ad_promoted_item": "ad_promoted_item_id",
    "keyword": "keyword_id",
    "search_term": "search_term_id",
    "review": "review_id",
    "review_insight": "review_insight_id",
    "metric": "metric_record_id",
}

_GETTERS = {
    "store": "get_store",
    "product": "get_product",
    "sku": "get_sku",
    "listing": "get_listing",
    "listing_item": "get_listing_item",
    "campaign": "get_campaign",
    "review": "get_review",
}


class Staging:
    """Canonical staging + validation + referential integrity."""

    def __init__(self, repository):
        self.repository = repository

    def stage(self, mutations, definition):
        valid = []
        invalid = []
        for mutation in mutations:
            reason = self._validate(mutation, definition)
            if reason:
                invalid.append((mutation, reason))
            else:
                valid.append(mutation)
        return valid, invalid

    def _validate(self, mutation, definition):
        if mutation.resource not in _RESOURCE_CLASSES:
            return "unknown canonical resource"
        if mutation.mutation_type not in (MUTATION_UPSERT, MUTATION_APPEND,
                                          MUTATION_TOMBSTONE):
            return "unknown mutation type"
        if mutation.mutation_type != MUTATION_TOMBSTONE and not mutation.entity:
            return "missing entity payload"
        referential = self._referential(mutation)
        if referential:
            return referential
        return None

    def _referential(self, mutation):
        resource = mutation.resource
        entity = mutation.entity or {}
        if resource == "sku" and entity.get("product_id"):
            if self.repository.get_product(mutation.tenant_id, entity["product_id"]) is None:
                return "missing parent product"
        if resource == "listing_item":
            if (entity.get("listing_id")
                    and self.repository.get_listing(mutation.tenant_id, entity["listing_id"]) is None):
                return "missing parent listing"
            if (entity.get("sku_id")
                    and self.repository.get_sku(mutation.tenant_id, entity["sku_id"]) is None):
                return "missing parent sku"
        return None


class PublishManager:
    """Applies canonical mutations to the Repository + ExternalIdentityMap.

    ``publish`` performs the whole partition unit (mutations + identity updates
    + tombstones) atomically: on PostgreSQL it runs in a single transaction so a
    mid-unit failure rolls back everything (Last Known Good preserved).
    """

    def __init__(self, repository, identity_map=None):
        self.repository = repository
        self.identity_map = identity_map
        self.tombstones = set()

    def publish(self, mutations, tombstones, definition, run):
        transaction = getattr(self.repository, "transaction", None)
        if transaction is not None:
            with transaction():
                return self._publish(mutations, tombstones, definition, run)
        return self._publish(mutations, tombstones, definition, run)

    def _publish(self, mutations, tombstones, definition, run):
        current_ids = {}
        for mutation in mutations:
            self._apply_mutation(mutation, definition, run, current_ids)
        for mutation in tombstones:
            self._apply_tombstone(mutation, definition, run)
        return {r: frozenset(ids) for r, ids in current_ids.items()}

    def apply(self, mutations, definition, run):
        """Backward-compatible single-apply (used by replay tests)."""
        return self.publish(mutations, (), definition, run)

    @staticmethod
    def current_ids(mutations):
        """Canonical subject ids produced by the mutations (without applying)."""
        current = {}
        for mutation in mutations:
            id_field = _RESOURCE_ID_FIELDS.get(mutation.resource)
            if id_field and id_field in (mutation.entity or {}):
                current.setdefault(mutation.resource, set()).add(
                    mutation.entity[id_field]
                )
        return {r: frozenset(ids) for r, ids in current.items()}

    def apply_tombstones(self, tombstones, definition, run):
        self.publish((), tombstones, definition, run)

    def _apply_mutation(self, mutation, definition, run, current_ids):
        if mutation.mutation_type == MUTATION_TOMBSTONE:
            return
        cls = _RESOURCE_CLASSES[mutation.resource]
        method = getattr(self.repository, _RESOURCE_METHODS[mutation.resource])
        entity = cls.from_dict(mutation.entity)
        method(definition.tenant_id, entity)
        if mutation.external_identity and self.identity_map is not None:
            from app.commerce.domain import ExternalIdentity
            self.identity_map.register(
                definition.tenant_id,
                ExternalIdentity(
                    tenant_id=definition.tenant_id,
                    platform=mutation.external_identity["platform"],
                    store_id=mutation.external_identity["store_id"],
                    resource_type=mutation.external_identity["resource_type"],
                    external_id=mutation.external_identity["external_id"],
                    canonical_id=mutation.external_identity["canonical_id"],
                ),
            )
        id_field = _RESOURCE_ID_FIELDS.get(mutation.resource)
        if id_field and id_field in mutation.entity:
            current_ids.setdefault(mutation.resource, set()).add(
                mutation.entity[id_field]
            )
        run.records_published += 1

    def _apply_tombstone(self, mutation, definition, run):
        if mutation.mutation_type != MUTATION_TOMBSTONE:
            return
        resource = mutation.resource
        subject_id = mutation.subject_id or (mutation.entity or {}).get("id")
        if subject_id is None:
            return
        self.tombstones.add((resource, subject_id))
        getter = _GETTERS.get(resource)
        if getter is not None:
            current = getattr(self.repository, getter)(
                definition.tenant_id, subject_id
            )
            if current is not None:
                payload = current.to_dict()
                if "status" in payload:
                    payload["status"] = "deleted"
                    cls = _RESOURCE_CLASSES[resource]
                    method = getattr(self.repository, _RESOURCE_METHODS[resource])
                    method(definition.tenant_id, cls.from_dict(payload))
        run.tombstones_generated += 1


__all__ = ["Staging", "PublishManager", "_RESOURCE_CLASSES"]
