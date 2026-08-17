"""Idempotency-Key contract tests (Phase 18.12.5)."""

from tests.product_api.conftest import AUTH


def test_message_idempotency_returns_same_execution(client):
    headers = {**AUTH, "Idempotency-Key": "msg-001"}
    first = client.post("/v1/agents/commerce_operations_agent/messages",
                        headers=headers, json={"message": "JP01 销量下降"})
    assert first.status_code == 200
    first_id = first.json()["execution"]["execution_id"]

    second = client.post("/v1/agents/commerce_operations_agent/messages",
                         headers=headers, json={"message": "JP01 销量下降"})
    assert second.status_code == 200
    assert second.json()["execution"]["execution_id"] == first_id


def test_message_same_key_different_payload_returns_409(client):
    headers = {**AUTH, "Idempotency-Key": "msg-conflict"}
    client.post("/v1/agents/commerce_operations_agent/messages",
                headers=headers, json={"message": "JP01 销量下降"})
    response = client.post("/v1/agents/commerce_operations_agent/messages",
                           headers=headers, json={"message": "其他问题"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_approval_idempotency_stable(client, application):
    application.business.approval.create_request(
        approval_id="approval_001", action_id="act1", tenant_id="company_A",
        requester="agent", action_type="UPDATE_AD_BUDGET", risk_level="HIGH")
    headers = {**AUTH, "Idempotency-Key": "approve-001"}
    first = client.post("/v1/approvals/approval_001/approve",
                        headers=headers, json={"comment": "ok"})
    assert first.status_code == 200
    second = client.post("/v1/approvals/approval_001/approve",
                         headers=headers, json={"comment": "ok"})
    assert second.status_code == 200
    assert second.json()["status"] == "APPROVED"


def test_reject_idempotency_stable(client, application):
    application.business.approval.create_request(
        approval_id="approval_002", action_id="act2", tenant_id="company_A",
        requester="agent", action_type="UPDATE_AD_BUDGET", risk_level="HIGH")
    headers = {**AUTH, "Idempotency-Key": "reject-001"}
    client.post("/v1/approvals/approval_002/reject",
                headers=headers, json={"comment": "no"})
    second = client.post("/v1/approvals/approval_002/reject",
                         headers=headers, json={"comment": "no"})
    assert second.status_code == 200
    assert second.json()["status"] == "REJECTED"


def test_invalid_idempotency_key_rejected(client):
    headers = {**AUTH, "Idempotency-Key": "bad key!"}
    response = client.post("/v1/agents/commerce_operations_agent/messages",
                           headers=headers, json={"message": "hi"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
