"""Execution + trace API tests (Phase 18.12)."""

from tests.product_api.conftest import AUTH


def _run_message(client):
    response = client.post(
        "/v1/agents/commerce_operations_agent/messages",
        headers=AUTH, json={"message": "JP01 销量下降"},
    )
    assert response.status_code == 200
    return response.json()["execution"]["execution_id"]


def test_get_execution(client, application):
    execution_id = _run_message(client)
    response = client.get(f"/v1/executions/{execution_id}", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["execution_id"] == execution_id
    assert body["status"] == "COMPLETED"
    assert body["agent_id"] == "commerce_operations_agent"


def test_get_execution_trace(client, application):
    execution_id = _run_message(client)
    response = client.get(f"/v1/executions/{execution_id}/trace", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["execution_id"] == execution_id
    assert body["trace_id"]


def test_get_unknown_execution(client):
    response = client.get("/v1/executions/nonexistent", headers=AUTH)
    assert response.status_code == 404
