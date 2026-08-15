"""Shared fixtures for the Commerce Sync (Phase 7) tests."""

from types import SimpleNamespace

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
from app.commerce.repositories.inmemory import (
    InMemoryCommerceRepository,
    InMemoryExternalIdentityMap,
)

TENANT = "company_A"


def product_record(sid, canonical_id, title, external_id=None, deleted=False,
                   invalid=False, sequence=None):
    record = {
        "id": sid,
        "resource": "product",
        "data": {"product_id": canonical_id, "title": title, "brand": "Acme",
                 "status": "active"},
        "deleted": deleted,
        "invalid": invalid,
    }
    if external_id:
        record["external_id"] = external_id
    if sequence:
        record["sequence"] = sequence
    return record


def metric_record(sid, metric_name, value, period_start, sequence=None):
    return {
        "id": sid,
        "resource": "metric",
        "data": {
            "metric_record_id": sid,
            "subject_type": "STORE",
            "subject_id": "JP01",
            "metric_name": metric_name,
            "metric_class": "AGGREGATED",
            "granularity": "DAILY",
            "period_start": period_start,
            "period_end": period_start,
            "value": value,
            "unit": "JPY",
        },
        "sequence": sequence,
    }


class Harness:
    """Builds a full sync pipeline over an in-memory canonical store."""

    def __init__(self):
        self.repository = InMemoryCommerceRepository()
        self.identity_map = InMemoryExternalIdentityMap()
        self.landing = RawLanding()
        self.quarantine = Quarantine()
        self.staging = Staging(self.repository)
        self.publish = PublishManager(self.repository, self.identity_map)
        self.lock = SyncLock()
        self.state_store = SyncStateStore()
        self.events = SyncEvents()
        self.registry = SyncDefinitionRegistry()
        self.adapters = {"fake": FakeAdapter(tenant_id=TENANT, store_id="JP01")}
        self.connectors = {}

    def make(self, sync_id, resource="product", mode="FULL_SNAPSHOT", records=None,
             fail_after_page=None, batch_size=100, lookback_window=0):
        self.connectors["fake"] = FakeConnector(
            records=records or [], fail_after_page=fail_after_page,
        )
        definition = SyncDefinition(
            sync_id=sync_id, version="1.0", tenant_id=TENANT, source="fake",
            store_id="JP01", resource=resource, mode=mode,
            connector_id="fake", adapter_id="fake", batch_size=batch_size,
            lookback_window=lookback_window,
        )
        self.registry.register(definition)
        coordinator = SyncCoordinator(
            self.registry, self.connectors, self.adapters, self.landing,
            self.quarantine, self.staging, self.publish, self.lock,
            self.state_store, self.events,
        )
        return coordinator, definition


@pytest.fixture
def harness():
    return Harness()


__all__ = [
    "TENANT", "Harness", "product_record", "metric_record",
]
