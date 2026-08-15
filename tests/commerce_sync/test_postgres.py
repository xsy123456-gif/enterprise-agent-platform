"""Phase 7 Sync Postgres integration tests (gated by COMMERCE_TEST_DATABASE_URL)."""

import os
import uuid

import pytest

from app.commerce.ingestion import (
    FakeAdapter,
    FakeConnector,
    PublishManager,
    Quarantine,
    RawLanding,
    Staging,
    SyncCoordinator,
    SyncDefinition,
    SyncDefinitionRegistry,
    SyncEvents,
    SyncLock,
    SyncStateStore,
)
from app.commerce.repositories.factory import build_identity_map, build_repository
from tests.commerce_sync.conftest import product_record

pytestmark = pytest.mark.skipif(
    not os.getenv("COMMERCE_TEST_DATABASE_URL"),
    reason="COMMERCE_TEST_DATABASE_URL is not configured",
)

_TABLES = [
    "commerce_external_identities",
    "commerce_metric_series",
    "commerce_inventory_snapshots",
    "commerce_reviews",
    "commerce_review_insights",
    "commerce_campaigns",
    "commerce_ad_groups",
    "commerce_ads",
    "commerce_ad_promoted_items",
    "commerce_keywords",
    "commerce_search_terms",
    "commerce_listing_items",
    "commerce_listings",
    "commerce_skus",
    "commerce_products",
    "commerce_stores",
]


def _cleanup(repository, tenant_id):
    with repository.connection_factory() as conn:
        with conn.cursor() as cursor:
            for table in _TABLES:
                cursor.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))


def _coordinator(repository, identity_map, tenant_id, sync_id, records):
    landing = RawLanding()
    quarantine = Quarantine()
    staging = Staging(repository)
    publish = PublishManager(repository, identity_map)
    lock = SyncLock()
    state_store = SyncStateStore()
    events = SyncEvents()
    registry = SyncDefinitionRegistry()
    adapters = {"fake": FakeAdapter(tenant_id=tenant_id, store_id="JP01")}
    connectors = {"fake": FakeConnector(records=records)}
    definition = SyncDefinition(
        sync_id=sync_id, version="1.0", tenant_id=tenant_id, source="fake",
        store_id="JP01", resource="product", mode="FULL_SNAPSHOT",
        connector_id="fake", adapter_id="fake",
    )
    registry.register(definition)
    coordinator = SyncCoordinator(
        registry, connectors, adapters, landing, quarantine, staging, publish,
        lock, state_store, events,
    )
    return coordinator


def test_full_snapshot_publishes_to_postgres():
    url = os.environ["COMMERCE_TEST_DATABASE_URL"]
    repository = build_repository(url, initialize=True)
    identity_map = build_identity_map(url)
    tenant = f"sync-test-{uuid.uuid4().hex}"
    sync_id = f"catalog.product.{tenant}"
    try:
        coordinator = _coordinator(
            repository, identity_map, tenant, sync_id,
            [product_record("s1", "product_A", "Widget", external_id="ASIN-A")],
        )
        run = coordinator.run(sync_id)
        assert run.status == "SUCCEEDED"
        assert repository.get_product(tenant, "product_A").title == "Widget"
        assert identity_map.resolve(
            tenant, "fake", "JP01", "product", "ASIN-A") == "product_A"
    finally:
        _cleanup(repository, tenant)
