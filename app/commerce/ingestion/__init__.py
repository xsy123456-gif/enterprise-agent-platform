"""Commerce ingestion — Connector / Adapter / Sync Core (Phase 7).

Platform-neutral Connector (transport) and Adapter (semantic mapping) feed a
versioned sync pipeline: Raw Landing -> Adapter -> Canonical Staging ->
validate/referential -> atomic publish -> tombstone (complete full snapshot
only) -> committed watermark advance -> domain events.  at-least-once fetch +
idempotent canonical write.
"""

from app.commerce.ingestion.coordinator import (
    SyncCoordinator,
    SyncCriticalFailure,
    SyncLockError,
)
from app.commerce.ingestion.envelope import (
    MUTATION_APPEND,
    MUTATION_TOMBSTONE,
    MUTATION_TYPES,
    MUTATION_UPSERT,
    CanonicalMutation,
    SourceRecordEnvelope,
    payload_checksum,
)
from app.commerce.ingestion.events import (
    EVENT_DATA_PUBLISHED,
    EVENT_SYNC_COMPLETED,
    SyncEvents,
)
from app.commerce.ingestion.fakes import FakeAdapter, FakeConnector
from app.commerce.ingestion.infra import (
    Quarantine,
    QuarantineRecord,
    RawLanding,
    SyncLock,
    SyncStateStore,
)
from app.commerce.ingestion.models import (
    RUN_CANCELLED,
    RUN_CREATED,
    RUN_FAILED,
    RUN_FETCHING,
    RUN_MAPPING,
    RUN_PARTIAL,
    RUN_PUBLISHING,
    RUN_SUCCEEDED,
    RUN_VALIDATING,
    SyncCheckpoint,
    SyncDefinition,
    SyncRun,
    utc_now,
)
from app.commerce.ingestion.ports import (
    SYNC_FULL_SNAPSHOT,
    SYNC_INCREMENTAL,
    SYNC_MODES,
    AdapterMappingError,
    AdapterPort,
    ConnectorPort,
    FetchRequest,
    FetchResult,
)
from app.commerce.ingestion.publish import PublishManager, Staging
from app.commerce.ingestion.registry import SyncDefinitionRegistry

__all__ = [
    "ConnectorPort",
    "AdapterPort",
    "AdapterMappingError",
    "FetchRequest",
    "FetchResult",
    "SYNC_FULL_SNAPSHOT",
    "SYNC_INCREMENTAL",
    "SYNC_MODES",
    "SourceRecordEnvelope",
    "CanonicalMutation",
    "MUTATION_UPSERT",
    "MUTATION_APPEND",
    "MUTATION_TOMBSTONE",
    "MUTATION_TYPES",
    "payload_checksum",
    "SyncDefinition",
    "SyncRun",
    "SyncCheckpoint",
    "utc_now",
    "SyncDefinitionRegistry",
    "FakeConnector",
    "FakeAdapter",
    "RawLanding",
    "Quarantine",
    "QuarantineRecord",
    "SyncLock",
    "SyncStateStore",
    "Staging",
    "PublishManager",
    "SyncCoordinator",
    "SyncLockError",
    "SyncCriticalFailure",
    "SyncEvents",
    "EVENT_SYNC_COMPLETED",
    "EVENT_DATA_PUBLISHED",
    "RUN_CREATED",
    "RUN_FETCHING",
    "RUN_MAPPING",
    "RUN_VALIDATING",
    "RUN_PUBLISHING",
    "RUN_SUCCEEDED",
    "RUN_PARTIAL",
    "RUN_FAILED",
    "RUN_CANCELLED",
]
