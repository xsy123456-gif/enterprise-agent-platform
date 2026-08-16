"""Agent + message API tests (Phase 18.12)."""

from tests.product_api.conftest import AUTH


def test_list_agents(client):
    response = client.get("/v1/agents", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert body["items"][0]["agent_id"] == "commerce_operations_agent"


def test_send_message_executes_agent(client, application):
    response = client.post(
        "/v1/agents/commerce_operations_agent/messages",
        headers=AUTH,
        json={"message": "JP01 最近销量下降原因"},
    )
    assert response.status_code == 200
    body = response.json()
    execution = body["execution"]
    assert execution and execution["execution_id"]
    assert body["response"]["content"]
    # the same execution_id must exist in the ExecutionManager
    record = application.commerce.execution_manager.store.get(
        execution["execution_id"])
    assert record is not None
    assert record.agent_id == "commerce_operations_agent"


def test_send_message_to_unknown_agent(client):
    response = client.post(
        "/v1/agents/unknown_agent/messages",
        headers=AUTH, json={"message": "hello"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
