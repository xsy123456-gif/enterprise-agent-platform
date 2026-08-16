"""Phase 12.9.5 TikTok connector + adapter tests."""

from app.commerce.ingestion.ports import FetchRequest
from app.commerce.integration.adapters.tiktok import TikTokAdapter
from app.commerce.integration.connectors.tiktok import TikTokConnector
from app.commerce.integration.credentials.models import Credential, SecretReference
from app.commerce.integration.credentials.provider import InMemorySecretProvider


def _credential():
    return Credential(
        credential_id="c1", tenant_id="company_A", provider="tiktok",
        secret_ref=SecretReference(reference_id="vault/tiktok/token"))


def _connector():
    records = [
        {"id": "p1", "resource": "product", "product_id": "1729001",
         "title": "Phone Case", "external_id": "1729001", "sequence": "1"},
        {"id": "p2", "resource": "product", "product_id": "1729002",
         "title": "Charger", "external_id": "1729002", "sequence": "2"},
    ]
    return TikTokConnector(
        records=records, credential=_credential(),
        secret_provider=InMemorySecretProvider({"vault/tiktok/token": "tok"}))


def test_tiktok_connector_fetches_dto():
    connector = _connector()
    page = connector.fetch(FetchRequest(resource="PRODUCT", mode="FULL_SNAPSHOT"))
    assert len(page.envelopes) == 2
    assert page.envelopes[0].source == "tiktok"
    assert page.envelopes[0].payload["product_id"] == "1729001"


def test_tiktok_adapter_maps_product_id_to_listing():
    adapter = TikTokAdapter(tenant_id="company_A", store_id="TT01")
    connector = _connector()
    page = connector.fetch(FetchRequest(resource="PRODUCT", mode="FULL_SNAPSHOT"))
    mutations = adapter.adapt(page.envelopes[0])
    assert mutations[0].resource == "listing"
    assert mutations[0].entity["listing_id"] == "listing_1729001"
    assert mutations[0].entity["platform"] == "tiktok"
    assert mutations[0].external_identity["external_id"] == "1729001"


def test_tiktok_adapter_no_business_analysis():
    adapter = TikTokAdapter(tenant_id="company_A", store_id="TT01")
    connector = _connector()
    page = connector.fetch(FetchRequest(resource="PRODUCT", mode="FULL_SNAPSHOT"))
    mutation = adapter.adapt(page.envelopes[0])[0]
    for forbidden in ("cause", "impact", "priority", "metric"):
        assert forbidden not in mutation.entity
