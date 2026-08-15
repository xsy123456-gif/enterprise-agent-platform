"""SyncCoordinator — drives the full sync pipeline.

Pipeline: fetch (paginated) -> Raw Landing -> Adapter map -> Canonical Staging ->
validate/referential -> atomic publish -> tombstone (complete full snapshot
only) -> advance committed watermark (only on full success) -> publish events.

The committed watermark advances ONLY after a fully successful
fetch + map + validate + publish; on failure the Last Known Good is retained.
"""

import uuid

from app.commerce.ingestion.envelope import (
    MUTATION_TOMBSTONE,
    CanonicalMutation,
)
from app.commerce.ingestion.events import (
    EVENT_DATA_PUBLISHED,
    EVENT_SYNC_COMPLETED,
)
from app.commerce.ingestion.infra import QuarantineRecord
from app.commerce.ingestion.models import (
    RUN_FETCHING,
    RUN_MAPPING,
    RUN_PUBLISHING,
    RUN_FAILED,
    RUN_SUCCEEDED,
    RUN_VALIDATING,
    SYNC_FULL_SNAPSHOT,
    SYNC_INCREMENTAL,
    SyncCheckpoint,
    SyncRun,
    utc_now,
)
from app.commerce.ingestion.ports import AdapterMappingError, FetchRequest


class SyncLockError(Exception):
    """The partition is already locked by another sync."""


class SyncCoordinator:

    def __init__(self, registry, connectors, adapters, landing, quarantine,
                 staging, publish, lock, state_store, events):
        self.registry = registry
        self.connectors = connectors
        self.adapters = adapters
        self.landing = landing
        self.quarantine = quarantine
        self.staging = staging
        self.publish = publish
        self.lock = lock
        self.state_store = state_store
        self.events = events

    def run(self, sync_id, trace_id=None):
        definition = self.registry.get(sync_id)
        connector = self.connectors[definition.connector_id]
        adapter = self.adapters[definition.adapter_id]
        partition_key = definition.partition_key

        lease = self.lock.acquire(partition_key)
        if lease is None:
            raise SyncLockError(f"sync already running for {partition_key}")

        state = self.state_store.get(sync_id) or SyncCheckpoint(sync_id=sync_id)
        run = SyncRun(
            sync_run_id=uuid.uuid4().hex,
            sync_id=sync_id,
            sync_version=definition.version,
            tenant_id=definition.tenant_id,
            source=definition.source,
            store_id=definition.store_id,
            resource=definition.resource,
            mode=definition.mode,
            committed_watermark_before=state.committed_watermark,
            connector_version=getattr(connector, "version", "1.0"),
            adapter_version=getattr(adapter, "version", "1.0"),
            sync_definition_version=definition.version,
            trace_id=trace_id or "",
        )
        try:
            self._execute(definition, connector, adapter, run, state)
        except Exception as error:  # noqa: BLE001 - Last Known Good on failure
            run.status = RUN_FAILED
            run.error_summary = str(error)
            run.completed_at = utc_now()
            # committed watermark NOT advanced; state NOT saved.
        finally:
            self.lock.release(partition_key, lease)
        return run

    def _execute(self, definition, connector, adapter, run, state):
        # ── FETCH ─────────────────────────────────────────────
        run.status = RUN_FETCHING
        envelopes = []
        cursor = None
        if definition.mode == SYNC_INCREMENTAL:
            cursor = state.committed_watermark
        full_complete = False
        while True:
            fetch = connector.fetch(FetchRequest(
                resource=definition.resource,
                mode=definition.mode,
                cursor=cursor,
                lookback=definition.lookback_window,
                limit=definition.batch_size,
            ))
            envelopes.extend(fetch.envelopes)
            for envelope in fetch.envelopes:
                self.landing.record(envelope)
            run.records_fetched += len(fetch.envelopes)
            cursor = fetch.next_cursor
            if fetch.complete:
                full_complete = True
                break
        run.working_cursor = cursor
        run.full_snapshot_complete = (
            definition.mode == SYNC_FULL_SNAPSHOT and full_complete
        )

        # ── MAP ───────────────────────────────────────────────
        run.status = RUN_MAPPING
        mutations = []
        for envelope in envelopes:
            try:
                mutations.extend(adapter.adapt(envelope))
            except AdapterMappingError as error:
                self.quarantine.record(QuarantineRecord(
                    sync_run_id=run.sync_run_id,
                    source_record_id=envelope.source_record_id,
                    resource=envelope.resource,
                    error_code="ADAPTER_MAPPING",
                    adapter_version=getattr(adapter, "version", "1.0"),
                    raw_reference=envelope.source_payload_checksum,
                ))
                run.records_quarantined += 1
        run.records_mapped = len(mutations)

        # ── STAGE + VALIDATE ──────────────────────────────────
        run.status = RUN_VALIDATING
        valid, invalid = self.staging.stage(mutations, definition)
        for _mutation, reason in invalid:
            self.quarantine.record(QuarantineRecord(
                sync_run_id=run.sync_run_id,
                source_record_id=_mutation.source_record_id,
                resource=_mutation.resource,
                error_code="VALIDATION",
                adapter_version=getattr(adapter, "version", "1.0"),
                raw_reference=reason,
            ))
            run.records_quarantined += 1
        run.records_staged = len(valid)

        # ── PUBLISH (atomic) ──────────────────────────────────
        run.status = RUN_PUBLISHING
        current_ids = self.publish.apply(valid, definition, run)

        # ── TOMBSTONE (complete full snapshot only) ───────────
        if definition.mode == SYNC_FULL_SNAPSHOT:
            if run.full_snapshot_complete:
                tombstones = self._tombstones(state, current_ids, definition)
                self.publish.apply_tombstones(tombstones, definition, run)
            else:
                run.error_summary = (
                    "incomplete full snapshot; tombstone generation suppressed"
                )

        # ── ADVANCE COMMITTED WATERMARK (only after full success)
        if definition.mode == SYNC_INCREMENTAL:
            state.committed_watermark = cursor
        state.working_cursor = cursor
        state.checkpoint_cursor = cursor
        state.last_snapshot_ids = {
            resource: frozenset(ids) for resource, ids in current_ids.items()
        }
        state.last_full_snapshot_complete = run.full_snapshot_complete
        self.state_store.save(state)
        run.committed_watermark_after = state.committed_watermark

        run.status = RUN_SUCCEEDED
        run.completed_at = utc_now()

        # ── EVENTS ────────────────────────────────────────────
        self.events.publish(EVENT_SYNC_COMPLETED, {
            "sync_id": definition.sync_id,
            "sync_run_id": run.sync_run_id,
            "status": run.status,
            "records_published": run.records_published,
        })
        self.events.publish(EVENT_DATA_PUBLISHED, {
            "sync_id": definition.sync_id,
            "resource": definition.resource,
            "records": run.records_published,
        })

    def _tombstones(self, state, current_ids, definition):
        previous = state.last_snapshot_ids.get(definition.resource, frozenset())
        current = current_ids.get(definition.resource, frozenset())
        absent = previous - current
        return [
            CanonicalMutation(
                mutation_type=MUTATION_TOMBSTONE,
                resource=definition.resource,
                tenant_id=definition.tenant_id,
                subject_id=subject_id,
            )
            for subject_id in sorted(absent)
        ]


__all__ = ["SyncCoordinator", "SyncLockError"]
