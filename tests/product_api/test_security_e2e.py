"""Security + full read-path E2E (Phase 18.12)."""

import pytest
from fastapi.testclient import TestClient

from app.api.factory import create_http_app
from app.api.auth import TestAuthenticationProvider
from app.api.config import api_config_for
from app.platform.agent_control import AgentAccessControl
from app.platform.agent_control.governance import AgentAccessPolicy
from tests.product_api.conftest import AUTH, seed_commerce


def _run_message(client):
    response = client.post(
        "/v1/agents/commerce_operations_agent/messages",
        headers=AUTH, json={"message": "JP01 销量下降"},
    )
    assert response.status_code == 200
    return response.json()


def test_full_read_path_e2e(client, application):
    body = _run_message(client)
    execution_id = body["execution"]["execution_id"]

    # 1. ExecutionRecord
    record = application.commerce.execution_manager.store.get(execution_id)
    assert record is not None

    # 2. Trace
    trace = application.production.trace.trace(record.trace_id)
    assert trace is not None
    assert trace.execution_id == execution_id

    # 3. Metric
    samples = application.production.metrics.samples(
        "commerce_operations_agent")
    assert any(s.execution_id == execution_id for s in samples)

    # 4. Evaluation
    evaluations = application.intelligence.evaluation_subscriber.evaluations()
    assert any(e.execution_id == execution_id for e in evaluations)


def test_unauthorized_agent_denied(http_app):
    # An empty AgentAccessControl denies every agent (fail-closed).
    deny = AgentAccessControl()
    app = create_http_app(http_app.state.application,
                          TestAuthenticationProvider(),
                          api_config_for("testing"), access_control=deny)
    client = TestClient(app)
    response = client.post(
        "/v1/agents/commerce_operations_agent/messages",
        headers=AUTH, json={"message": "JP01 销量下降"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_authorized_agent_allowed(http_app):
    allow = AgentAccessControl([AgentAccessPolicy(
        policy_id="p1", agent_id="commerce_operations_agent",
        subject_type="user", subject_id="U001", permission="agent.execute")])
    app = create_http_app(http_app.state.application,
                          TestAuthenticationProvider(),
                          api_config_for("testing"), access_control=allow)
    client = TestClient(app)
    response = client.post(
        "/v1/agents/commerce_operations_agent/messages",
        headers=AUTH, json={"message": "JP01 销量下降"},
    )
    assert response.status_code == 200


def test_cross_tenant_execution_isolated(client, application):
    body = _run_message(client)
    execution_id = body["execution"]["execution_id"]

    # Simulate a different-tenant access via the gateway directly.
    from types import SimpleNamespace
    gateway = client.app.state.gateway
    other_tenant = SimpleNamespace(tenant_id="company_B", principal_id="U001")
    from app.api.errors import ApiError
    with pytest.raises(ApiError) as exc:
        gateway.get_execution(other_tenant, execution_id)
    assert exc.value.code == "RESOURCE_NOT_FOUND"


def test_trace_contains_no_secret(client):
    body = _run_message(client)
    execution_id = body["execution"]["execution_id"]
    response = client.get(f"/v1/executions/{execution_id}/trace",
                          headers=AUTH)
    assert response.status_code == 200
    text = response.text.lower()
    for forbidden in ("authorization", "api_key", "refresh_token", "secret",
                      "bearer", "password"):
        assert forbidden not in text


def test_error_contract_shape(client):
    response = client.get("/v1/executions/does-not-exist", headers=AUTH)
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert "request_id" in body["error"]
