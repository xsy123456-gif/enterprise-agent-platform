"""Health + authentication + request validation tests (Phase 18.12)."""

from tests.product_api.conftest import AUTH


def test_health_live(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_health_ready(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_no_auth_returns_401(client):
    response = client.get("/v1/agents")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_invalid_auth_returns_401(client):
    response = client.get("/v1/agents",
                          headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def test_security_field_injection_rejected(client):
    response = client.post(
        "/v1/agents/commerce_operations_agent/messages",
        headers=AUTH,
        json={"message": "show stores", "tenant_id": "other_tenant",
              "role": "admin", "permissions": ["*"]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_empty_message_rejected(client):
    response = client.post(
        "/v1/agents/commerce_operations_agent/messages",
        headers=AUTH, json={"message": "   "},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
