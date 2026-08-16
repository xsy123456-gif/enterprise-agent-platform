"""TikTok connector (fake) — Phase 12.9.5.

Transport-only connector serving canned TikTok Shop DTOs (PRODUCT / ORDER /
INVENTORY / ADVERTISING / REVIEW).  Not the production TikTok API.
"""

from app.commerce.ingestion.envelope import SourceRecordEnvelope
from app.commerce.ingestion.ports import FetchRequest, FetchResult
from app.commerce.integration.connectors.base import BaseConnector


class TikTokConnector(BaseConnector):
    connector_id = "tiktok_shop"

    def __init__(self, records=None, version="1.0", **kwargs):
        super().__init__(version=version, **kwargs)
        self.records = list(records or [])
        self.fetch_count = 0

    def _fetch(self, request: FetchRequest) -> FetchResult:
        self.fetch_count += 1
        self.authorize()
        if request.mode == "INCREMENTAL":
            return self._incremental(request)
        return self._full(request)

    def _full(self, request):
        offset = int(request.cursor) if request.cursor and str(request.cursor).isdigit() else 0
        batch = self.records[offset:offset + request.limit]
        next_offset = offset + len(batch)
        return FetchResult(
            envelopes=tuple(self._envelope(record) for record in batch),
            next_cursor=None if next_offset >= len(self.records) else str(next_offset),
            complete=next_offset >= len(self.records),
        )

    def _incremental(self, request):
        cursor = request.cursor or ""
        candidates = sorted(
            (r for r in self.records if str(r.get("sequence", "")) > str(cursor)),
            key=lambda r: str(r.get("sequence", "")),
        )
        batch = candidates[:request.limit]
        last = batch[-1].get("sequence") if batch else cursor
        return FetchResult(
            envelopes=tuple(self._envelope(record) for record in batch),
            next_cursor=last if batch else cursor,
            complete=len(candidates) <= request.limit,
        )

    def _envelope(self, record):
        return SourceRecordEnvelope(
            source_record_id=record["id"],
            resource=record["resource"],
            source="tiktok",
            payload=dict(record),
            sequence=record.get("sequence"),
            source_external_id=record.get("external_id", ""),
            connector_id=self.connector_id,
            connector_version=self.version,
        )


__all__ = ["TikTokConnector"]
