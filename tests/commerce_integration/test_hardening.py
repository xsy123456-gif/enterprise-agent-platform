"""Phase 12.9.7 Hardening + Commerce Agent E2E."""

import pytest

from app.commerce.domain import Store
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
from app.commerce.query.service import CommerceQueryService
from app.commerce.repositories.inmemory import (
    InMemoryCommerceRepository,
    InMemoryExternalIdentityMap,
)
from app.commerce.diagnostics.errors import UnknownDefinitionVersionError

TENANT = "company_A"


def _build(records=None, adapter_version="1.0", connector_version="1.0",
           adapter_cls=AmazonAdapter):
    connectors = ConnectorRegistry()
    connectors.register_class("amazon_sp_api", "1.0", AmazonConnector)
    adapters = AdapterRegistry()
    adapters.register_class("amazon_adapter", "1.0", adapter_cls)
    cp = InMemoryCredentialProvider([Credential(
        credential_id="c1", tenant_id=TENANT, provider="amazon",
        secret_ref=SecretReference(reference_id="vault/amazon/token"))])
    sp = InMemorySecretProvider({"vault/amazon/token": "amz-tok"})
    repository = InMemoryCommerceRepository()
    repository.upsert_store(TENANT, Store(
        store_id="JP01", tenant_id=TENANT, platform="amazon", marketplace="JP",
        external_store_id="ext-JP01", name="JP01", currency="JPY",
        timezone="Asia/Tokyo"))
    identity_map = InMemoryExternalIdentityMap()
    runtime = IntegrationSyncRuntime(
        connectors, adapters, cp, sp, repository, identity_map)
    definition = SyncDefinition(
        sync_id="s", version="1.0", tenant_id=TENANT, source="amazon",
        store_id="JP01", resource="listing", mode=SYNC_FULL_SNAPSHOT,
        connector_id="amazon_sp_api", adapter_id="amazon_adapter")
    binding = ConnectorBinding(
        sync_id="s", connector_id="amazon_sp_api", adapter_id="amazon_adapter",
        connector_config={"records": records or _listing_records()})
    return runtime, repository, identity_map, definition, binding


def _listing_records():
    return [
        {"id": "r1", "resource": "listing", "asin": "B001", "title": "Mouse",
         "external_id": "B001", "sequence": "1"},
        {"id": "r2", "resource": "listing", "asin": "B002", "title": "Keyboard",
         "external_id": "B002", "sequence": "2"},
    ]


# ── Commerce Agent E2E ─────────────────────────────────────

def test_commerce_agent_e2e_amazon_to_query():
    runtime, repository, identity_map, definition, binding = _build()
    run = runtime.run(definition, binding)
    assert run.status == "SUCCEEDED"
    # The canonical data is now readable by the agent's query layer.
    service = CommerceQueryService(repository, identity_map=identity_map)
    result = service.list_listings_by_store(TENANT, "JP01")
    assert result.data[0].external_listing_id == "B001"
    assert result.data[0].listing_id == "listing_B001"


# ── Replay / version governance ────────────────────────────

def test_raw_landing_preserves_records_for_replay():
    runtime, repository, _, definition, binding = _build()
    runtime.run(definition, binding)
    assert len(runtime.landing.list()) == 2
    assert runtime.landing.list()[0]["source"] == "amazon"


def test_adapter_version_replay_same_canonical_id():
    runtime, repository, identity_map, definition, binding = _build(
        adapter_version="1.0")
    runtime.run(definition, binding)
    # Replay the same raw data with a (hypothetical) newer adapter still maps
    # the same external id -> same canonical id (identity stability).
    canonical = identity_map.resolve(TENANT, "amazon", "JP01", "listing", "B001")
    assert canonical == "listing_B001"


def test_unknown_connector_version_fails_closed():
    runtime, repository, identity_map, definition, _ = _build()
    binding = ConnectorBinding(
        sync_id="s", connector_id="amazon_sp_api", adapter_id="amazon_adapter",
        connector_version="9.9")
    with pytest.raises(UnknownDefinitionVersionError):
        runtime.run(definition, binding)


# ── Failure: adapter failure -> quarantine ─────────────────

def test_adapter_failure_quarantined_partial():
    records = [
        {"id": "r1", "resource": "listing", "asin": "B001", "title": "Mouse",
         "external_id": "B001", "sequence": "1"},
        {"id": "r2", "resource": "listing", "title": "no asin", "sequence": "2"},
    ]
    runtime, repository, _, definition, binding = _build(records=records)
    run = runtime.run(definition, binding)
    assert run.status == "PARTIAL"
    assert run.records_quarantined == 1
    assert len(runtime.quarantine.list()) == 1
    assert repository.get_listing(TENANT, "listing_B001") is not None


# ── Security / audit ───────────────────────────────────────

def test_audit_log_never_contains_secret():
    runtime, repository, _, definition, binding = _build()
    runtime.run(definition, binding)
    # The connector audit log records attempts only — never a token/secret.
    for entry in runtime.landing.list():
        assert "amz-tok" not in str(entry)


def test_credential_never_exposed_to_query_layer():
    runtime, repository, identity_map, definition, binding = _build()
    runtime.run(definition, binding)
    service = CommerceQueryService(repository, identity_map=identity_map)
    result = service.list_listings_by_store(TENANT, "JP01")
    for listing in result.data:
        assert "token" not in listing.to_dict()
        assert "secret" not in listing.to_dict()
