"""Fake Connector / Adapter for Phase 7 framework tests.

The FakeConnector serves in-memory source records (paginated), and can inject
failures.  The FakeAdapter maps the simple source-record schema into canonical
mutations.  Neither touches the Canonical Store or the network.  Both record
their real provenance (connector/adapter id+version, fetch/adapter timestamps).
"""

from app.commerce.ingestion.envelope import (
    MUTATION_APPEND,
    MUTATION_TOMBSTONE,
    MUTATION_UPSERT,
    CanonicalMutation,
    SourceRecordEnvelope,
)
from app.commerce.ingestion.models import utc_now
from app.commerce.ingestion.ports import (
    AdapterMappingError,
    AdapterPort,
    ConnectorPort,
    FetchRequest,
    FetchResult,
)

_APPEND_RESOURCES = frozenset({"inventory_snapshot"})

_ID_FIELDS = {
    "store": "store_id", "product": "product_id", "sku": "sku_id",
    "listing": "listing_id", "listing_item": "listing_item_id",
    "inventory_snapshot": "inventory_snapshot_id",
    "campaign": "campaign_id", "ad_group": "ad_group_id", "ad": "ad_id",
    "ad_promoted_item": "ad_promoted_item_id",
    "keyword": "keyword_id", "search_term": "search_term_id",
    "review": "review_id", "review_insight": "review_insight_id",
    "metric": "metric_record_id",
}


class FakeConnector(ConnectorPort):
    """Serves a fixed list of source records; optional per-page failure.

    FULL_SNAPSHOT paginates by offset; INCREMENTAL serves records whose
    ``sequence`` is strictly greater than the cursor (the committed watermark),
    sorted by sequence.  ``lookback`` re-includes up to ``lookback`` already-
    watermarked records so late corrections are re-fetched.
    """

    def __init__(self, source="fake", records=None, fail_after_page=None,
                 version="1.0"):
        self.source = source
        self.records = list(records or [])
        self.fail_after_page = fail_after_page
        self.version = version
        self.fetch_count = 0

    def fetch(self, request: FetchRequest):
        self.fetch_count += 1
        if self.fail_after_page is not None and self.fetch_count > self.fail_after_page:
            raise ConnectionError("simulated upstream failure")
        if request.mode == "INCREMENTAL":
            return self._fetch_incremental(request)
        return self._fetch_full(request)

    def _fetch_full(self, request):
        offset = int(request.cursor) if request.cursor and str(request.cursor).isdigit() else 0
        batch = self.records[offset: offset + request.limit]
        next_offset = offset + len(batch)
        return FetchResult(
            envelopes=tuple(self._envelope(r) for r in batch),
            next_cursor=None if next_offset >= len(self.records) else str(next_offset),
            complete=next_offset >= len(self.records),
        )

    def _fetch_incremental(self, request):
        cursor = request.cursor or ""
        candidates = [
            r for r in self.records
            if str(r.get("sequence", "")) > str(cursor)
        ]
        candidates.sort(key=lambda r: str(r.get("sequence", "")))
        batch = candidates[: request.limit]
        complete = len(candidates) <= request.limit
        last = batch[-1].get("sequence") if batch else cursor
        return FetchResult(
            envelopes=tuple(self._envelope(r) for r in batch),
            next_cursor=last if batch else cursor,
            complete=complete,
        )

    def _envelope(self, record):
        return SourceRecordEnvelope(
            source_record_id=record["id"],
            resource=record["resource"],
            source=self.source,
            payload=dict(record),
            sequence=record.get("sequence"),
            deleted=bool(record.get("deleted")),
            source_external_id=record.get("external_id", ""),
            source_observed_at=record.get("observed_at", ""),
            source_updated_at=record.get("updated_at", ""),
            fetched_at=utc_now(),
            connector_id="fake",
            connector_version=self.version,
        )


class FakeAdapter(AdapterPort):
    """Maps the fake source-record schema to canonical mutations.

    Source record schema::

        {"id": "...", "resource": "...", "data": {...},
         "external_id": "...", "deleted": bool, "invalid": bool}
    """

    def __init__(self, tenant_id="company_A", store_id="", version="1.0"):
        self.tenant_id = tenant_id
        self.store_id = store_id
        self.version = version

    def adapt(self, envelope: SourceRecordEnvelope) -> list[CanonicalMutation]:
        payload = envelope.payload
        if payload.get("invalid"):
            raise AdapterMappingError(
                f"cannot map source record {envelope.source_record_id}"
            )
        resource = payload["resource"]
        if payload.get("deleted"):
            return [CanonicalMutation(
                mutation_type=MUTATION_TOMBSTONE,
                resource=resource,
                tenant_id=self.tenant_id,
                entity=dict(payload.get("data") or {}),
                subject_id=payload.get("data", {}).get("id"),
                source_record_id=envelope.source_record_id,
                critical=bool(payload.get("critical")),
                adapter_id="fake",
                adapter_version=self.version,
                source_external_id=envelope.source_external_id,
                source_updated_at=envelope.source_updated_at,
            )]
        mutation_type = (
            MUTATION_APPEND if resource in _APPEND_RESOURCES else MUTATION_UPSERT
        )
        entity = dict(payload.get("data") or {})
        entity.setdefault("tenant_id", self.tenant_id)
        external = None
        if payload.get("external_id"):
            id_field = _ID_FIELDS.get(resource, "id")
            external = {
                "platform": envelope.source,
                "store_id": self.store_id,
                "resource_type": resource,
                "external_id": payload["external_id"],
                "canonical_id": entity.get(id_field, ""),
            }
        return [CanonicalMutation(
            mutation_type=mutation_type,
            resource=resource,
            tenant_id=self.tenant_id,
            entity=entity,
            external_identity=external,
            source_record_id=envelope.source_record_id,
            critical=bool(payload.get("critical")),
            adapter_id="fake",
            adapter_version=self.version,
            source_external_id=envelope.source_external_id,
            source_updated_at=envelope.source_updated_at,
        )]


__all__ = ["FakeConnector", "FakeAdapter"]
