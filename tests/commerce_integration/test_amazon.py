"""Phase 12.9.4 Amazon connector + adapter tests."""

import pytest

from app.commerce.ingestion.ports import AdapterMappingError, FetchRequest
from app.commerce.integration.adapters.amazon import AmazonAdapter
from app.commerce.integration.connectors.amazon import AmazonConnector
from app.commerce.integration.credentials.models import Credential, SecretReference
from app.commerce.integration.credentials.provider import InMemorySecretProvider
from app.commerce.integration.errors import CredentialError


def _credential():
    return Credential(
        credential_id="c1", tenant_id="company_A", provider="amazon",
        secret_ref=SecretReference(reference_id="vault/amazon/token"))


def _records():
    return [
        {"id": "r1", "resource": "listing", "asin": "B001",
         "title": "Wireless Mouse", "price": 29.99, "external_id": "B001",
         "sequence": "1"},
        {"id": "r2", "resource": "listing", "asin": "B002",
         "title": "Keyboard", "price": 49.99, "external_id": "B002",
         "sequence": "2"},
        {"id": "r3", "resource": "inventory", "sku": "SKU-1", "quantity": 42,
         "external_id": "SKU-1", "sequence": "3"},
    ]


def _connector(**kwargs):
    kwargs.setdefault("credential", _credential())
    kwargs.setdefault("secret_provider",
                      InMemorySecretProvider({"vault/amazon/token": "tok"}))
    return AmazonConnector(records=_records(), **kwargs)


def test_amazon_connector_paginates():
    connector = _connector()
    page1 = connector.fetch(FetchRequest(resource="LISTING", mode="FULL_SNAPSHOT",
                                         limit=2))
    assert len(page1.envelopes) == 2
    assert page1.complete is False
    assert page1.next_cursor == "2"
    page2 = connector.fetch(FetchRequest(resource="LISTING", mode="FULL_SNAPSHOT",
                                         limit=2, cursor=page1.next_cursor))
    assert len(page2.envelopes) == 1
    assert page2.complete is True


def test_amazon_connector_requires_credential():
    connector = AmazonConnector(records=_records())  # no credential/secret
    with pytest.raises(CredentialError):
        connector.fetch(FetchRequest(resource="LISTING", mode="FULL_SNAPSHOT"))


def test_amazon_connector_emits_dto_not_canonical():
    connector = _connector()
    page = connector.fetch(FetchRequest(resource="LISTING", mode="FULL_SNAPSHOT",
                                        limit=1))
    envelope = page.envelopes[0]
    assert envelope.source == "amazon"
    assert envelope.payload["asin"] == "B001"
    assert "listing_id" not in envelope.payload  # connector never maps


def test_amazon_adapter_maps_asin_to_listing():
    adapter = AmazonAdapter(tenant_id="company_A", store_id="JP01")
    connector = _connector()
    page = connector.fetch(FetchRequest(resource="LISTING", mode="FULL_SNAPSHOT",
                                        limit=1))
    mutations = adapter.adapt(page.envelopes[0])
    assert mutations[0].resource == "listing"
    assert mutations[0].entity["listing_id"] == "listing_B001"
    assert mutations[0].external_identity["external_id"] == "B001"
    assert mutations[0].external_identity["canonical_id"] == "listing_B001"


def test_amazon_adapter_maps_inventory_as_append():
    adapter = AmazonAdapter(tenant_id="company_A", store_id="JP01")
    connector = _connector()
    page = connector.fetch(FetchRequest(resource="INVENTORY",
                                        mode="FULL_SNAPSHOT", limit=1))
    # third record is inventory; fetch all then filter
    all_records = connector.fetch(FetchRequest(resource="INVENTORY",
                                               mode="FULL_SNAPSHOT", limit=10))
    inventory = [e for e in all_records.envelopes if e.resource == "inventory"][0]
    mutations = adapter.adapt(inventory)
    assert mutations[0].mutation_type == "APPEND"
    assert mutations[0].resource == "inventory_snapshot"


def test_amazon_adapter_invalid_record_raises():
    adapter = AmazonAdapter(tenant_id="company_A", store_id="JP01")
    from app.commerce.ingestion.envelope import SourceRecordEnvelope
    envelope = SourceRecordEnvelope(
        source_record_id="x", resource="listing", source="amazon",
        payload={"resource": "listing", "title": "no asin"})
    with pytest.raises(AdapterMappingError):
        adapter.adapt(envelope)
