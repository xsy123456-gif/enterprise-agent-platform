"""Phase 7 Final Gate Hardening tests: lease, provenance, required vs optional."""

from app.commerce.ingestion import (
    RUN_FAILED,
    RUN_PARTIAL,
    SYNC_FULL_SNAPSHOT,
    SyncLock,
)
from app.commerce.ingestion.envelope import SourceRecordEnvelope
from tests.commerce_sync.conftest import TENANT, product_record


# ── Lease semantics ─────────────────────────────────────────

def test_lease_blocks_until_expiry():
    clock = [0]
    lock = SyncLock(clock=lambda: clock[0])
    lease = lock.acquire("p", owner="A", lease_seconds=10)
    assert lease is not None
    assert lock.is_locked("p")
    assert lock.acquire("p", owner="B") is None
    clock[0] = 11  # expire
    assert not lock.is_locked("p")
    assert lock.acquire("p", owner="B") is not None


def test_lease_renew_extends():
    clock = [0]
    lock = SyncLock(clock=lambda: clock[0])
    lease = lock.acquire("p", owner="A", lease_seconds=10)
    clock[0] = 5
    assert lock.renew("p", lease.token, lease_seconds=10) is True
    clock[0] = 12  # would have expired without renew
    assert lock.is_locked("p")


def test_stale_token_cannot_release_after_reacquire():
    clock = [0]
    lock = SyncLock(clock=lambda: clock[0])
    lease1 = lock.acquire("p", owner="A", lease_seconds=10)
    clock[0] = 20  # expire
    lease2 = lock.acquire("p", owner="B")
    assert lease2 is not None
    assert lock.release("p", lease1.token) is False  # stale owner can't release
    assert lock.is_locked("p")
    assert lock.release("p", lease2.token) is True


def test_stale_token_cannot_renew():
    clock = [0]
    lock = SyncLock(clock=lambda: clock[0])
    lease1 = lock.acquire("p", owner="A", lease_seconds=10)
    clock[0] = 20
    lease2 = lock.acquire("p", owner="B")
    assert lock.renew("p", lease1.token) is False  # stale token can't renew
    assert lock.is_locked("p")
    assert lock.release("p", lease2.token)


# ── Provenance propagation ──────────────────────────────────

def test_envelope_carries_connector_provenance(harness):
    coordinator, _ = harness.make(
        "catalog.product", resource="product", mode=SYNC_FULL_SNAPSHOT,
        records=[product_record("s1", "product_A", "Widget", external_id="ASIN-A")],
    )
    coordinator.run("catalog.product")
    landed = harness.landing.list()[0]
    assert landed["connector_id"] == "fake"
    assert landed["connector_version"] == "1.0"
    assert landed["fetched_at"]
    assert landed["source_external_id"] == "ASIN-A"


def test_mutation_carries_adapter_provenance(harness):
    envelope = SourceRecordEnvelope(
        source_record_id="s1", resource="product", source="fake",
        payload=product_record("s1", "product_A", "Widget", external_id="ASIN-A"),
        source_external_id="ASIN-A", source_updated_at="2026-08-01T00:00:00+00:00",
        connector_id="fake", connector_version="1.0", fetched_at="now",
    )
    mutation = harness.adapters["fake"].adapt(envelope)[0]
    assert mutation.adapter_id == "fake"
    assert mutation.adapter_version == "1.0"
    assert mutation.source_external_id == "ASIN-A"
    assert mutation.source_updated_at == "2026-08-01T00:00:00+00:00"
    assert mutation.critical is False


def test_run_records_versions(harness):
    coordinator, _ = harness.make(
        "catalog.product", resource="product", mode=SYNC_FULL_SNAPSHOT,
        records=[product_record("s1", "product_A", "Widget")],
    )
    run = coordinator.run("catalog.product")
    assert run.connector_version == "1.0"
    assert run.adapter_version == "1.0"
    assert run.sync_definition_version == "1.0"


# ── Required (critical) vs optional failure ─────────────────

def test_critical_record_failure_fails_partition(harness):
    coordinator, _ = harness.make(
        "catalog.product", resource="product", mode=SYNC_FULL_SNAPSHOT,
        records=[
            product_record("s1", "product_A", "Widget"),
            product_record("s2", "product_B", "Gadget", invalid=True),
        ],
    )
    # Make product_B critical by injecting "critical" into the record.
    harness.connectors["fake"].records[1]["critical"] = True
    run = coordinator.run("catalog.product")
    assert run.status == RUN_FAILED
    assert run.records_published == 0
    assert harness.repository.get_product(TENANT, "product_A") is None
    assert harness.repository.get_product(TENANT, "product_B") is None
    assert harness.state_store.get("catalog.product") is None  # no watermark


def test_optional_record_failure_is_partial(harness):
    coordinator, _ = harness.make(
        "catalog.product", resource="product", mode=SYNC_FULL_SNAPSHOT,
        records=[
            product_record("s1", "product_A", "Widget"),
            product_record("s2", "product_B", "Gadget", invalid=True),
        ],
    )
    run = coordinator.run("catalog.product")
    assert run.status == RUN_PARTIAL
    assert run.records_published == 1
    assert run.records_quarantined == 1
    assert harness.repository.get_product(TENANT, "product_A") is not None
    assert harness.repository.get_product(TENANT, "product_B") is None
