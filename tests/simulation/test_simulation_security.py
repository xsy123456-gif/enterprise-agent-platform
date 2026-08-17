"""Phase 18.13.5 simulation security tests.

Provider scope isolation, control-endpoint protection, credential redaction,
and production must not auto-use simulation.
"""

from fastapi.testclient import TestClient

from simulation.amazon.app import build_app as amazon_app


def test_provider_scope_isolation():
    # A token bound to store-002 must not read store-001 data.
    client = TestClient(amazon_app())
    response = client.get("/amazon/v1/listings", params={"seller_id": "store-001"},
                          headers={"Authorization": "Bearer sim-amazon-store-002-token"})
    assert response.status_code == 404


def test_control_endpoint_rejects_provider_credential():
    client = TestClient(amazon_app())
    response = client.post("/__simulation__/control/fail-next",
                           headers={"Authorization": "Bearer sim-amazon-key"})
    assert response.status_code == 401


def test_credentials_never_logged():
    client = TestClient(amazon_app())
    client.get("/amazon/v1/listings", params={"seller_id": "store-001"},
               headers={"Authorization": "Bearer super-secret-token"})
    logs = client.app.state.store.request_log.list()
    assert logs
    assert "super-secret-token" not in str(logs)
    assert "Bearer" not in str(logs)


def test_production_does_not_auto_use_simulation(monkeypatch):
    from types import SimpleNamespace

    from app.composition.enterprise import _build_external_integrations

    monkeypatch.setenv("EXTERNAL_INTEGRATION_MODE", "simulation")
    commerce = SimpleNamespace(
        repository=None, identity_map=None,
        execution_manager=SimpleNamespace(event_bus=None),
    )
    assert _build_external_integrations("production", commerce) is None

    # and in a non-production environment with simulation mode enabled, it IS
    # wired (repo required to build the sync runtime).
    from app.commerce.repositories.inmemory import InMemoryCommerceRepository
    commerce = SimpleNamespace(
        repository=InMemoryCommerceRepository(), identity_map=None,
        execution_manager=SimpleNamespace(event_bus=None),
    )
    assert _build_external_integrations("testing", commerce) is not None
