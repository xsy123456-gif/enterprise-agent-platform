"""Phase 18.13.1 Simulation foundation tests."""

from fastapi.testclient import TestClient

from simulation.amazon.app import build_app


def _client():
    return TestClient(build_app())


def test_health_returns_ok():
    response = _client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "provider": "amazon"}


def test_invalid_credential_is_401():
    client = _client()
    response = client.get("/amazon/v1/listings", params={"seller_id": "store-001"},
                          headers={"Authorization": "Bearer wrong-token"})
    assert response.status_code == 401


def test_valid_credential_reads_listings():
    client = _client()
    response = client.get("/amazon/v1/listings", params={"seller_id": "store-001"},
                          headers={"Authorization": "Bearer sim-amazon-key"})
    assert response.status_code == 200
    assert response.json()["items"][0]["sellerSku"] == "SKU-001"


def test_reset_clears_state_and_requires_admin():
    client = _client()
    # control endpoint requires the admin token, not the provider credential
    response = client.post("/__simulation__/reset",
                           headers={"Authorization": "Bearer sim-amazon-key"})
    assert response.status_code == 401

    response = client.post("/__simulation__/reset",
                           headers={"X-Simulation-Admin-Token": "simulation-admin-token"})
    assert response.status_code == 200
    assert response.json() == {"status": "reset"}


def test_request_log_does_not_record_credentials():
    client = _client()
    secret = "sim-amazon-key"
    client.get("/amazon/v1/listings", params={"seller_id": "store-001"},
               headers={"Authorization": f"Bearer {secret}"})
    store = client.app.state.store
    logs = store.request_log.list()
    assert logs, "expected at least one logged request"
    serialized = str(logs)
    assert secret not in serialized
    assert "Authorization" not in serialized
