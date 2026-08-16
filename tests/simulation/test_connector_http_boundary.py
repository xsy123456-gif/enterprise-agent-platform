"""Phase 18.13.5 connector -> real localhost TCP socket boundary tests.

The Amazon/TikTok/SAP/Salesforce/NetSuite connectors talk to the simulation
services over an actual TCP socket (uvicorn), not ASGI in-process.
"""

from app.commerce.ingestion.ports import FetchRequest
from app.commerce.integration.connectors import (
    AmazonHttpConnector,
    NetSuiteHttpConnector,
    SalesforceHttpConnector,
    SapHttpConnector,
    TikTokHttpConnector,
)
from app.commerce.integration.credentials.models import Credential, SecretReference
from app.commerce.integration.credentials.provider import InMemorySecretProvider
from tests.simulation.conftest import run_simulation

from simulation.amazon.app import build_app as amazon_app
from simulation.netsuite.app import build_app as netsuite_app
from simulation.salesforce.app import build_app as salesforce_app
from simulation.sap.app import build_app as sap_app
from simulation.tiktok.app import build_app as tiktok_app


def _secret(provider):
    return InMemorySecretProvider({f"sim/{provider}/token": f"sim-{provider}-key"})


def _credential(provider):
    return Credential(credential_id=f"{provider}-sim", tenant_id="company_A",
                      provider=provider,
                      secret_ref=SecretReference(reference_id=f"sim/{provider}/token"))


def test_amazon_connector_crosses_real_socket():
    with run_simulation(amazon_app()) as server:
        connector = AmazonHttpConnector(
            base_url=server.base_url, scope={"seller_id": "store-001"},
            credential=_credential("amazon"), secret_provider=_secret("amazon"))
        connector.set_correlation_id("corr-amazon-1")
        result = connector.fetch(FetchRequest(resource="listing",
                                              mode="FULL_SNAPSHOT"))
        assert len(result.envelopes) == 4
        assert result.envelopes[0].source == "amazon"
        assert result.envelopes[0].payload["asin"] == "B0ABC001"

        logs = server.app.state.store.request_log.list()
        assert any(e["path"] == "/amazon/v1/listings"
                   and e["correlation_id"] == "corr-amazon-1" for e in logs)


def test_tiktok_connector_crosses_real_socket():
    with run_simulation(tiktok_app()) as server:
        connector = TikTokHttpConnector(
            base_url=server.base_url, scope={"shop_id": "shop-001"},
            credential=_credential("tiktok"), secret_provider=_secret("tiktok"))
        result = connector.fetch(FetchRequest(resource="product",
                                              mode="FULL_SNAPSHOT"))
        assert len(result.envelopes) == 3
        assert result.envelopes[0].payload["product_id"] == "7230001"


def test_erp_crm_connectors_cross_real_socket():
    cases = [
        (sap_app(), SapHttpConnector, {"plant": "PL01", "company_code": "CC01"},
         "sap", "material", "MATNR"),
        (salesforce_app(), SalesforceHttpConnector, {}, "salesforce", "account",
         "Id"),
        (netsuite_app(), NetSuiteHttpConnector, {"subsidiary": "SUB-001"},
         "netsuite", "item", "internalId"),
    ]
    for app, cls, scope, provider, resource, id_field in cases:
        with run_simulation(app) as server:
            connector = cls(base_url=server.base_url, scope=scope,
                            credential=_credential(provider),
                            secret_provider=_secret(provider))
            result = connector.fetch(FetchRequest(resource=resource,
                                                  mode="FULL_SNAPSHOT"))
            assert result.envelopes, f"{provider} fetched nothing"
            assert result.envelopes[0].payload[id_field]


def test_amazon_write_via_connector_mutates_simulation_state():
    with run_simulation(amazon_app()) as server:
        connector = AmazonHttpConnector(
            base_url=server.base_url, scope={"seller_id": "store-001"},
            credential=_credential("amazon"), secret_provider=_secret("amazon"))
        updated = connector.update_campaign("CMP-AMZ-1", {
            "sellerId": "store-001", "dailyBudget": 120.0, "state": "ENABLED"})
        assert updated["dailyBudget"] == 120.0

        campaigns = connector.fetch(FetchRequest(resource="campaign",
                                                 mode="FULL_SNAPSHOT"))
        campaign = next(c for c in campaigns.envelopes
                        if c.payload["campaignId"] == "CMP-AMZ-1")
        assert campaign.payload["dailyBudget"] == 120.0

        logs = server.app.state.store.request_log.list()
        assert any(e["method"] == "PATCH" for e in logs)
