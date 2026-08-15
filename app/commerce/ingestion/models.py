"""Sync domain models: SyncDefinition, SyncRun, SyncCheckpoint, statuses."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.commerce.ingestion.ports import SYNC_FULL_SNAPSHOT, SYNC_INCREMENTAL

# SyncRun statuses (§96)
RUN_CREATED = "CREATED"
RUN_FETCHING = "FETCHING"
RUN_MAPPING = "MAPPING"
RUN_VALIDATING = "VALIDATING"
RUN_PUBLISHING = "PUBLISHING"
RUN_SUCCEEDED = "SUCCEEDED"
RUN_PARTIAL = "PARTIAL"
RUN_FAILED = "FAILED"
RUN_CANCELLED = "CANCELLED"
RUN_STATUSES = frozenset({
    RUN_CREATED, RUN_FETCHING, RUN_MAPPING, RUN_VALIDATING, RUN_PUBLISHING,
    RUN_SUCCEEDED, RUN_PARTIAL, RUN_FAILED, RUN_CANCELLED,
})


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SyncDefinition:
    """A versioned Platform x Resource sync definition (§82)."""

    sync_id: str
    version: str
    tenant_id: str
    source: str
    store_id: str
    resource: str
    mode: str = SYNC_FULL_SNAPSHOT
    connector_id: str = "fake"
    adapter_id: str = "fake"
    batch_size: int = 100
    lookback_window: int = 0
    cursor_strategy: str = "sequence"
    watermark_strategy: str = "after_publish"
    publish_policy: str = "atomic"
    schema_version: str = "1.0"
    depends_on: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "depends_on", tuple(self.depends_on or ()))
        if self.mode not in (SYNC_FULL_SNAPSHOT, SYNC_INCREMENTAL):
            raise ValueError(f"unknown sync mode: {self.mode}")

    @property
    def partition_key(self):
        return f"{self.tenant_id}:{self.source}:{self.store_id}:{self.resource}"

    def to_dict(self) -> dict:
        return {
            "sync_id": self.sync_id,
            "version": self.version,
            "tenant_id": self.tenant_id,
            "source": self.source,
            "store_id": self.store_id,
            "resource": self.resource,
            "mode": self.mode,
            "connector_id": self.connector_id,
            "adapter_id": self.adapter_id,
            "batch_size": self.batch_size,
            "lookback_window": self.lookback_window,
            "cursor_strategy": self.cursor_strategy,
            "watermark_strategy": self.watermark_strategy,
            "publish_policy": self.publish_policy,
            "schema_version": self.schema_version,
            "depends_on": list(self.depends_on),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SyncDefinition":
        return cls(
            sync_id=data["sync_id"],
            version=data["version"],
            tenant_id=data["tenant_id"],
            source=data["source"],
            store_id=data["store_id"],
            resource=data["resource"],
            mode=data.get("mode", SYNC_FULL_SNAPSHOT),
            connector_id=data.get("connector_id", "fake"),
            adapter_id=data.get("adapter_id", "fake"),
            batch_size=data.get("batch_size", 100),
            lookback_window=data.get("lookback_window", 0),
            cursor_strategy=data.get("cursor_strategy", "sequence"),
            watermark_strategy=data.get("watermark_strategy", "after_publish"),
            publish_policy=data.get("publish_policy", "atomic"),
            schema_version=data.get("schema_version", "1.0"),
            depends_on=tuple(data.get("depends_on", ())),
        )


@dataclass
class SyncRun:
    """A first-class sync execution record (§96)."""

    sync_run_id: str
    sync_id: str
    sync_version: str
    tenant_id: str
    source: str
    store_id: str
    resource: str
    mode: str
    status: str = RUN_CREATED
    started_at: str = field(default_factory=utc_now)
    completed_at: str = ""
    records_fetched: int = 0
    records_mapped: int = 0
    records_staged: int = 0
    records_published: int = 0
    records_quarantined: int = 0
    working_cursor: str | None = None
    committed_watermark_before: str | None = None
    committed_watermark_after: str | None = None
    full_snapshot_complete: bool = False
    tombstones_generated: int = 0
    connector_version: str = ""
    adapter_version: str = ""
    sync_definition_version: str = ""
    error_summary: str = ""
    trace_id: str = ""

    def to_dict(self) -> dict:
        return {
            "sync_run_id": self.sync_run_id,
            "sync_id": self.sync_id,
            "sync_version": self.sync_version,
            "tenant_id": self.tenant_id,
            "source": self.source,
            "store_id": self.store_id,
            "resource": self.resource,
            "mode": self.mode,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "records_fetched": self.records_fetched,
            "records_mapped": self.records_mapped,
            "records_staged": self.records_staged,
            "records_published": self.records_published,
            "records_quarantined": self.records_quarantined,
            "working_cursor": self.working_cursor,
            "committed_watermark_before": self.committed_watermark_before,
            "committed_watermark_after": self.committed_watermark_after,
            "full_snapshot_complete": self.full_snapshot_complete,
            "tombstones_generated": self.tombstones_generated,
            "connector_version": self.connector_version,
            "adapter_version": self.adapter_version,
            "sync_definition_version": self.sync_definition_version,
            "error_summary": self.error_summary,
            "trace_id": self.trace_id,
        }


@dataclass
class SyncCheckpoint:
    """working cursor / checkpoint / committed watermark separation (§89)."""

    sync_id: str
    working_cursor: str | None = None
    checkpoint_cursor: str | None = None
    committed_watermark: str | None = None
    last_snapshot_ids: dict = field(default_factory=dict)
    last_full_snapshot_complete: bool = False

    def to_dict(self) -> dict:
        return {
            "sync_id": self.sync_id,
            "working_cursor": self.working_cursor,
            "checkpoint_cursor": self.checkpoint_cursor,
            "committed_watermark": self.committed_watermark,
            "last_snapshot_ids": {
                k: sorted(v) for k, v in self.last_snapshot_ids.items()
            },
            "last_full_snapshot_complete": self.last_full_snapshot_complete,
        }


__all__ = [
    "SyncDefinition",
    "SyncRun",
    "SyncCheckpoint",
    "utc_now",
    "RUN_CREATED",
    "RUN_FETCHING",
    "RUN_MAPPING",
    "RUN_VALIDATING",
    "RUN_PUBLISHING",
    "RUN_SUCCEEDED",
    "RUN_PARTIAL",
    "RUN_FAILED",
    "RUN_CANCELLED",
    "RUN_STATUSES",
]
