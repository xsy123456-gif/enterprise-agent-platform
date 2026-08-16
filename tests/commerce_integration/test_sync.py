"""Phase 12.9.6 Sync integration tests (Amazon -> canonical)."""

from app.commerce.ingestion.models import SyncDefinition
from app.commerce.ingestion.ports import SYNC_FULL_SNAPSHOT
from app.commerce.integration.adapters.amazon import AmazonAdapter
from app.commerce.integration.connectors.amazon import AmazonConnector
from app.commerce.integration.credentials.models import Credential, SecretReference
from app.commerce.integration.credentials.provider import (
    InMemoryCredentialProvider,
    InMemorySecretProvider,
)
from app.commerce.integration.registry import AdapterRegistry, ConnectorRegistry
from app.commerce.integration.sync import ConnectorBinding, IntegrationSyncRuntime
from app.commerce.repositories.inmemory import (
    InMemoryCommerceRepository,
    InMemoryExternalIdentityMap,
)

TENANT = "company_A"
LISTING_RECORDS = [
    {"id": "r1", "resource": "listing", "asin": "B001", "title": "Mouse",
     "external_id": "B001", "sequence": "1"},
    {"id": "r2", "resource": "listing", "asin": "B002", "title": "Keyboard",
     "external_id": "B002", "sequence": "2"},
]


def _runtime():
    connectors = ConnectorRegistry()
    connectors.register_class("amazon_sp_api", "1.0", AmazonConnector)
    adapters = AdapterRegistry()
    adapters.register_class("amazon_adapter", "1.0", AmazonAdapter)
    credential_provider = InMemoryCredentialProvider([Credential(
        credential_id="c1", tenant_id=TENANT, provider="amazon",
        secret_ref=SecretReference(reference_id="vault/amazon/token"))])
    secret_provider = InMemorySecretProvider({"vault/amazon/token": "amz-tok"})
    repository = InMemoryCommerceRepository()
    from app.commerce.domain import Store
    repository.upsert_store(TENANT, Store(
        store_id="JP01", tenant_id=TENANT, platform="amazon", marketplace="JP",
        external_store_id="ext-JP01", name="JP01", currency="JPY",
        timezone="Asia/Tokyo"))
    identity_map = InMemoryExternalIdentityMap()
    return IntegrationSyncRuntime(
        connectors, adapters, credential_provider, secret_provider,
        repository, identity_map), repository, identity_map


def _definition():
    return SyncDefinition(
        sync_id="amazon_jp_listing_sync", version="1.0",
        tenant_id=TENANT, source="amazon", store_id="JP01",
        resource="listing", mode=SYNC_FULL_SNAPSHOT,
        connector_id="amazon_sp_api", adapter_id="amazon_adapter",
    )


def _binding():
    return ConnectorBinding(
        sync_id="amazon_jp_listing_sync",
        connector_id="amazon_sp_api", adapter_id="amazon_adapter",
        connector_config={"records": LISTING_RECORDS},
    )


def test_amazon_listing_sync_to_canonical():
    runtime, repository, identity_map = _runtime()
    run = runtime.run(_definition(), _binding())
    assert run.status == "SUCCEEDED"
    assert run.records_published == 2
    listing = repository.get_listing(TENANT, "listing_B001")
    assert listing is not None
    assert listing.external_listing_id == "B001"
    assert listing.platform == "amazon"


def test_identity_mapping_same_external_same_canonical():
    runtime, repository, identity_map = _runtime()
    runtime.run(_definition(), _binding())
    assert identity_map.resolve(TENANT, "amazon", "JP01", "listing", "B001") == \
        "listing_B001"


def test_sync_idempotent_rerun():
    runtime, repository, identity_map = _runtime()
    runtime.run(_definition(), _binding())
    second = runtime.run(_definition(), _binding())
    assert second.status == "SUCCEEDED"
    assert len(repository.list_listings_by_store(TENANT, "JP01")) == 2
    # same external id still maps to the same canonical id (no conflict)
    assert identity_map.resolve(TENANT, "amazon", "JP01", "listing", "B001") == \
        "listing_B001"


def test_scheduler_runs_registered_syncs():
    runtime, repository, _ = _runtime()
    from app.commerce.integration.sync import SyncScheduler
    scheduler = SyncScheduler(runtime)
    scheduler.register(_definition(), _binding())
    results = scheduler.run_all()
    assert results["amazon_jp_listing_sync"].status == "SUCCEEDED"
    assert repository.get_listing(TENANT, "listing_B002") is not None
