"""Phase 7 Sync E2E tests: happy / failure / idempotency / history-correction /
tombstone / quarantine / lock / replay."""

import pytest

from app.commerce.ingestion import (
    RUN_FAILED,
    RUN_SUCCEEDED,
    SYNC_FULL_SNAPSHOT,
    SYNC_INCREMENTAL,
    SyncLockError,
)
from tests.commerce_sync.conftest import TENANT, metric_record, product_record


# ── Happy E2E ───────────────────────────────────────────────

def test_happy_full_snapshot(harness):
    coordinator, definition = harness.make(
        "catalog.product", resource="product", mode=SYNC_FULL_SNAPSHOT,
        records=[
            product_record("s1", "product_A", "Widget", external_id="ASIN-A"),
            product_record("s2", "product_B", "Gadget", external_id="ASIN-B"),
        ],
    )
    run = coordinator.run("catalog.product")
    assert run.status == RUN_SUCCEEDED
    assert run.records_fetched == 2
    assert run.records_published == 2
    assert harness.repository.get_product(TENANT, "product_A").title == "Widget"
    assert harness.repository.get_product(TENANT, "product_B").title == "Gadget"
    # ExternalIdentityMap was populated.
    assert harness.identity_map.resolve(
        TENANT, "fake", "JP01", "product", "ASIN-A") == "product_A"
    # Events fired.
    assert harness.events.completed_events()
    assert harness.events.published_events()
    # Raw landing recorded.
    assert len(harness.landing.list()) == 2


# ── Failure E2E (Last Known Good) ───────────────────────────

def test_failure_no_publish_no_watermark_advance(harness):
    coordinator, definition = harness.make(
        "catalog.product", resource="product", mode=SYNC_FULL_SNAPSHOT,
        records=[product_record("s1", "product_A", "Widget")],
        fail_after_page=0,  # first page fails
    )
    run = coordinator.run("catalog.product")
    assert run.status == RUN_FAILED
    assert harness.repository.get_product(TENANT, "product_A") is None
    assert not harness.events.completed_events()
    # No checkpoint saved -> no watermark advancement (Last Known Good).
    assert harness.state_store.get("catalog.product") is None


# ── Idempotency ─────────────────────────────────────────────

def test_idempotent_resync(harness):
    records = [product_record("s1", "product_A", "Widget")]
    coordinator, _ = harness.make(
        "catalog.product", resource="product", mode=SYNC_FULL_SNAPSHOT,
        records=records,
    )
    coordinator.run("catalog.product")
    run2 = coordinator.run("catalog.product")
    assert run2.status == RUN_SUCCEEDED
    assert run2.records_published == 1  # upserted, not duplicated
    assert harness.repository.list_products(TENANT).__len__() == 1


# ── History correction ──────────────────────────────────────

def test_history_correction(harness):
    coordinator, _ = harness.make(
        "catalog.product", resource="product", mode=SYNC_FULL_SNAPSHOT,
        records=[product_record("s1", "product_A", "Old Title")],
    )
    coordinator.run("catalog.product")
    # Corrected source data re-syncs over the same canonical id.
    harness.connectors["fake"].records = [
        product_record("s1", "product_A", "New Title"),
    ]
    coordinator.run("catalog.product")
    assert harness.repository.get_product(TENANT, "product_A").title == "New Title"
    assert harness.repository.list_products(TENANT).__len__() == 1


# ── Tombstone (complete full snapshot) ──────────────────────

def test_tombstone_on_complete_full_snapshot(harness):
    coordinator, _ = harness.make(
        "catalog.product", resource="product", mode=SYNC_FULL_SNAPSHOT,
        records=[
            product_record("s1", "product_A", "Widget"),
            product_record("s2", "product_B", "Gadget"),
        ],
    )
    coordinator.run("catalog.product")
    # Next full snapshot no longer contains product_B.
    harness.connectors["fake"].records = [product_record("s1", "product_A", "Widget")]
    run = coordinator.run("catalog.product")
    assert run.status == RUN_SUCCEEDED
    assert run.tombstones_generated == 1
    assert harness.repository.get_product(TENANT, "product_B").status == "deleted"


def test_no_tombstone_on_incomplete_full_snapshot(harness):
    coordinator, _ = harness.make(
        "catalog.product", resource="product", mode=SYNC_FULL_SNAPSHOT,
        records=[
            product_record("s1", "product_A", "Widget"),
            product_record("s2", "product_B", "Gadget"),
        ],
        batch_size=1,
    )
    coordinator.run("catalog.product")
    # Second run fails mid-fetch (page 2 fails) -> incomplete snapshot.
    harness.connectors["fake"].records = [
        product_record("s1", "product_A", "Widget"),
        product_record("s2", "product_B", "Gadget"),
    ]
    harness.connectors["fake"].fail_after_page = 1
    run = coordinator.run("catalog.product")
    assert run.status == RUN_FAILED
    assert run.tombstones_generated == 0
    # product_B remains active (Last Known Good, no tombstone inference).
    assert harness.repository.get_product(TENANT, "product_B").status == "active"


# ── Quarantine ──────────────────────────────────────────────

def test_adapter_failure_quarantined(harness):
    coordinator, _ = harness.make(
        "catalog.product", resource="product", mode=SYNC_FULL_SNAPSHOT,
        records=[
            product_record("s1", "product_A", "Widget"),
            product_record("s2", "product_B", "Gadget", invalid=True),
        ],
    )
    run = coordinator.run("catalog.product")
    assert run.status == RUN_SUCCEEDED
    assert run.records_quarantined == 1
    assert run.records_published == 1
    assert harness.repository.get_product(TENANT, "product_A") is not None
    assert harness.repository.get_product(TENANT, "product_B") is None
    assert len(harness.quarantine.list()) == 1
    assert harness.quarantine.list()[0].error_code == "ADAPTER_MAPPING"


def test_referential_integrity_failure_quarantined(harness):
    # A SKU referencing a missing parent product is quarantined at staging.
    coordinator, _ = harness.make(
        "catalog.sku", resource="sku", mode=SYNC_FULL_SNAPSHOT,
        records=[{
            "id": "s1", "resource": "sku",
            "data": {"sku_id": "sku_1", "product_id": "missing_product",
                     "merchant_sku": "SKU-1"},
        }],
    )
    run = coordinator.run("catalog.sku")
    assert run.records_quarantined == 1
    assert run.records_published == 0
    assert any(q.error_code == "VALIDATION" for q in harness.quarantine.list())


# ── Lock / Lease ────────────────────────────────────────────

def test_sync_lock_prevents_concurrent_writer(harness):
    coordinator, definition = harness.make(
        "catalog.product", resource="product", mode=SYNC_FULL_SNAPSHOT,
        records=[product_record("s1", "product_A", "Widget")],
    )
    # Manually hold the lock, then attempt to run.
    token = harness.lock.acquire(definition.partition_key)
    with pytest.raises(SyncLockError):
        coordinator.run("catalog.product")
    harness.lock.release(definition.partition_key, token)
    assert coordinator.run("catalog.product").status == RUN_SUCCEEDED


# ── Replay ──────────────────────────────────────────────────

def test_replay_from_raw_landing(harness):
    coordinator, definition = harness.make(
        "catalog.product", resource="product", mode=SYNC_FULL_SNAPSHOT,
        records=[product_record("s1", "product_A", "Widget")],
    )
    coordinator.run("catalog.product")
    landed = harness.landing.list()
    assert landed
    # Re-adapt the raw envelopes and re-publish (replay without re-fetching).
    from app.commerce.ingestion.envelope import SourceRecordEnvelope
    mutations = []
    for raw in landed:
        envelope = SourceRecordEnvelope.from_dict(raw)
        mutations.extend(harness.adapters["fake"].adapt(envelope))
    valid, _invalid = harness.staging.stage(mutations, definition)
    run = type("_Run", (), {"records_published": 0})()
    harness.publish.apply(valid, definition, run)
    assert run.records_published == 1


# ── INCREMENTAL watermark ───────────────────────────────────

def test_incremental_watermark_advances_only_on_success(harness):
    records = [
        metric_record("m1", "GMV", 100.0, "2026-08-01", sequence="1"),
        metric_record("m2", "GMV", 200.0, "2026-08-02", sequence="2"),
        metric_record("m3", "GMV", 300.0, "2026-08-03", sequence="3"),
    ]
    coordinator, _ = harness.make(
        "sales.metrics", resource="metric", mode=SYNC_INCREMENTAL,
        records=records, batch_size=1,
    )
    run = coordinator.run("sales.metrics")
    assert run.status == RUN_SUCCEEDED
    state = harness.state_store.get("sales.metrics")
    assert state.committed_watermark == "3"
    # A new record with a higher sequence is picked up on the next run.
    harness.connectors["fake"].records = records + [
        metric_record("m4", "GMV", 400.0, "2026-08-04", sequence="4"),
    ]
    run2 = coordinator.run("sales.metrics")
    assert run2.status == RUN_SUCCEEDED
    assert harness.state_store.get("sales.metrics").committed_watermark == "4"
    rows = harness.repository.query_metrics(TENANT, "STORE", "JP01", ["GMV"])
    assert len(rows) == 4
