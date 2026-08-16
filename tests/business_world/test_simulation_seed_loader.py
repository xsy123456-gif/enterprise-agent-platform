"""Phase 18.14 simulation seed loader + HTTP visibility tests."""

from fastapi.testclient import TestClient

from simulation.amazon.app import build_app as amazon_app
from simulation.tiktok.app import build_app as tiktok_app
from tests.business_world.conftest import SEED_ROOT
from tests.simulation.conftest import run_simulation


def test_seed_health_reports_dataset_version():
    client = TestClient(amazon_app(seed_path=SEED_ROOT))
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["dataset_id"] == "enterprise-commerce-v1"
    assert body["dataset_version"] == "1.0.0"


def test_seed_visible_over_http_amazon():
    from app.commerce.ingestion.ports import FetchRequest
    from app.commerce.integration.connectors import AmazonHttpConnector
    from app.commerce.integration.credentials.models import Credential, SecretReference
    from app.commerce.integration.credentials.provider import InMemorySecretProvider

    with run_simulation(amazon_app(seed_path=SEED_ROOT)) as server:
        connector = AmazonHttpConnector(
            base_url=server.base_url, scope={"seller_id": "seller-aurora-jp"},
            credential=Credential(credential_id="c", tenant_id="tenant_aurora",
                                  provider="amazon",
                                  secret_ref=SecretReference(reference_id="ref")),
            secret_provider=InMemorySecretProvider({"ref": "sim-amazon-key"}))
        result = connector.fetch(FetchRequest(resource="listing",
                                              mode="FULL_SNAPSHOT"))
        assert len(result.envelopes) == 14  # Aurora Amazon JP listings
        asins = {e.payload["asin"] for e in result.envelopes}
        assert "B0SIM001" in asins  # seeded (not contract fixture) data


def test_seed_visible_over_http_tiktok():
    from app.commerce.ingestion.ports import FetchRequest
    from app.commerce.integration.connectors import TikTokHttpConnector
    from app.commerce.integration.credentials.models import Credential, SecretReference
    from app.commerce.integration.credentials.provider import InMemorySecretProvider

    with run_simulation(tiktok_app(seed_path=SEED_ROOT)) as server:
        connector = TikTokHttpConnector(
            base_url=server.base_url, scope={"shop_id": "shop-aurora-us"},
            credential=Credential(credential_id="c", tenant_id="tenant_aurora",
                                  provider="tiktok",
                                  secret_ref=SecretReference(reference_id="ref")),
            secret_provider=InMemorySecretProvider({"ref": "sim-tiktok-key"}))
        result = connector.fetch(FetchRequest(resource="product",
                                              mode="FULL_SNAPSHOT"))
        assert result.envelopes
        product_ids = {e.payload["product_id"] for e in result.envelopes}
        assert "760000001" in product_ids


def test_reset_restores_seed_snapshot():
    client = TestClient(amazon_app(seed_path=SEED_ROOT))
    headers = {"Authorization": "Bearer sim-amazon-key"}
    # mutate a campaign via PATCH
    client.patch("/amazon/v1/advertising/campaigns/CMP-AMZJP-1",
                 headers=headers,
                 json={"sellerId": "seller-aurora-jp", "dailyBudget": 999.0,
                       "state": "ENABLED"})
    campaigns = client.get("/amazon/v1/advertising/campaigns",
                           params={"seller_id": "seller-aurora-jp"},
                           headers=headers).json()["items"]
    assert any(c["dailyBudget"] == 999.0 for c in campaigns)

    # reset restores the seeded baseline
    client.post("/__simulation__/reset",
                headers={"X-Simulation-Admin-Token": "simulation-admin-token"})
    campaigns = client.get("/amazon/v1/advertising/campaigns",
                           params={"seller_id": "seller-aurora-jp"},
                           headers=headers).json()["items"]
    assert all(c["dailyBudget"] != 999.0 for c in campaigns)


def test_seed_multi_tenant_isolation():
    # Northstar token must not read Aurora's Amazon seller records.
    client = TestClient(amazon_app(seed_path=SEED_ROOT))
    response = client.get(
        "/amazon/v1/listings", params={"seller_id": "seller-aurora-jp"},
        headers={"Authorization": "Bearer sim-amazon-store-002-token"})
    assert response.status_code == 404
