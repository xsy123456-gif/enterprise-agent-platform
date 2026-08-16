"""Phase 18.13.5 ingestion HTTP integration tests.

HTTP simulation -> connector -> SyncCoordinator -> adapter -> canonical publish,
with pagination, idempotent rerun, and external update handling.
"""

from app.commerce.domain import Store
from app.commerce.ingestion.models import SyncDefinition
from app.commerce.ingestion.ports import SYNC_FULL_SNAPSHOT
from app.commerce.integration.sync import ConnectorBinding, IntegrationSyncRuntime
from app.commerce.repositories.inmemory import (
    InMemoryCommerceRepository,
    InMemoryExternalIdentityMap,
)
from app.composition.external_integrations import (
    SimulationConnectorConfig,
    build_simulation_external_integrations,
)
from tests.simulation.conftest import run_simulation

from simulation.amazon.app import build_app as amazon_app
from simulation.sap.app import build_app as sap_app


def _repository():
    repository = InMemoryCommerceRepository()
    repository.upsert_store("company_A", Store(
        store_id="JP01", tenant_id="company_A", platform="amazon",
        marketplace="JP", external_store_id="ext-JP01", name="JP01",
        currency="JPY", timezone="Asia/Tokyo"))
    return repository


def _runtime(ext, repository):
    identity_map = InMemoryExternalIdentityMap()
    runtime = IntegrationSyncRuntime(
        ext.connector_registry, ext.adapter_registry, ext.credential_provider,
        ext.secret_provider, repository, identity_map)
    return runtime, identity_map


def test_amazon_listing_sync_paginates_over_http():
    with run_simulation(amazon_app()) as server:
        ext = build_simulation_external_integrations(
            "testing",
            config=SimulationConnectorConfig(amazon_base_url=server.base_url))
        repository = _repository()
        runtime, identity_map = _runtime(ext, repository)
        definition = SyncDefinition(
            sync_id="amazon_listing_sync", version="1.0", tenant_id="company_A",
            source="amazon", store_id="JP01", resource="listing",
            mode=SYNC_FULL_SNAPSHOT, connector_id="amazon_sp_api",
            adapter_id="amazon_adapter", batch_size=2)
        binding = ConnectorBinding(
            sync_id="amazon_listing_sync", connector_id="amazon_sp_api",
            adapter_id="amazon_adapter",
            connector_config={"base_url": server.base_url,
                              "scope": {"seller_id": "store-001"}})
        run = runtime.run(definition, binding)
        assert run.status == "SUCCEEDED"
        assert run.records_fetched == 4      # two pages (batch_size=2)
        assert run.records_published == 4
        assert run.full_snapshot_complete is True

        listings = repository.list_listings_by_store("company_A", "JP01")
        assert len(listings) == 4
        assert identity_map.resolve("company_A", "amazon", "JP01", "listing",
                                    "B0ABC001") == "listing_B0ABC001"


def test_amazon_sync_is_idempotent_and_handles_update():
    with run_simulation(amazon_app()) as server:
        ext = build_simulation_external_integrations(
            "testing",
            config=SimulationConnectorConfig(amazon_base_url=server.base_url))
        repository = _repository()
        runtime, identity_map = _runtime(ext, repository)
        definition = SyncDefinition(
            sync_id="amazon_listing_sync", version="1.0", tenant_id="company_A",
            source="amazon", store_id="JP01", resource="listing",
            mode=SYNC_FULL_SNAPSHOT, connector_id="amazon_sp_api",
            adapter_id="amazon_adapter", batch_size=100)
        binding = ConnectorBinding(
            sync_id="amazon_listing_sync", connector_id="amazon_sp_api",
            adapter_id="amazon_adapter",
            connector_config={"base_url": server.base_url,
                              "scope": {"seller_id": "store-001"}})

        runtime.run(definition, binding)
        # idempotent rerun -> same canonical count
        runtime.run(definition, binding)
        assert len(repository.list_listings_by_store("company_A", "JP01")) == 4

        # external update: change title in the simulation, re-sync -> updated
        server.app.state.store.upsert("listing", "asin", {
            "sellerSku": "SKU-001", "asin": "B0ABC001",
            "itemName": "Wireless Mouse v2", "status": "Active"})
        runtime.run(definition, binding)
        listing = repository.get_listing("company_A", "listing_B0ABC001")
        assert listing.title == "Wireless Mouse v2"


def test_sap_material_sync_publishes_canonical_product():
    with run_simulation(sap_app()) as server:
        ext = build_simulation_external_integrations(
            "testing",
            config=SimulationConnectorConfig(sap_base_url=server.base_url))
        repository = _repository()
        runtime, _ = _runtime(ext, repository)
        definition = SyncDefinition(
            sync_id="sap_material_sync", version="1.0", tenant_id="company_A",
            source="sap", store_id="JP01", resource="material",
            mode=SYNC_FULL_SNAPSHOT, connector_id="sap_erp",
            adapter_id="sap_adapter", batch_size=100)
        binding = ConnectorBinding(
            sync_id="sap_material_sync", connector_id="sap_erp",
            adapter_id="sap_adapter",
            connector_config={"base_url": server.base_url,
                              "scope": {"plant": "PL01", "company_code": "CC01"}})
        run = runtime.run(definition, binding)
        assert run.status == "SUCCEEDED"
        assert run.records_published == 3
        product = repository.get_product("company_A", "product_SKU-001")
        assert product is not None
        assert product.title == "Wireless Mouse"
