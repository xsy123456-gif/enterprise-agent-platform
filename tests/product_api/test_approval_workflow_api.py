"""Approval + workflow API tests (Phase 18.12)."""

from app.platform.business.workflow import BusinessWorkflow, WorkflowStep
from tests.product_api.conftest import AUTH


def _create_pending_approval(application):
    return application.business.approval.create_request(
        approval_id="approval_001", action_id="act1", tenant_id="company_A",
        requester="agent", action_type="UPDATE_AD_BUDGET", risk_level="HIGH",
    )


def test_list_approvals(client, application):
    _create_pending_approval(application)
    response = client.get("/v1/approvals", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert any(a["approval_id"] == "approval_001" for a in body["items"])


def test_approve(client, application):
    _create_pending_approval(application)
    response = client.post("/v1/approvals/approval_001/approve",
                           headers=AUTH, json={"comment": "ok"})
    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"


def test_reject(client, application):
    _create_pending_approval(application)
    response = client.post("/v1/approvals/approval_001/reject",
                           headers=AUTH, json={"comment": "no"})
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"


def test_approve_invalid_state(client, application):
    _create_pending_approval(application)
    client.post("/v1/approvals/approval_001/approve", headers=AUTH,
                json={"comment": "ok"})
    response = client.post("/v1/approvals/approval_001/reject",
                           headers=AUTH, json={"comment": "no"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"


def _start_wait_workflow(application):
    workflow = BusinessWorkflow(
        workflow_id="w", version="1.0",
        steps=[
            WorkflowStep(step_id="w1", step_type="WAIT", next_steps=("n1",)),
            WorkflowStep(step_id="n1", step_type="NOTIFICATION"),
        ],
    )
    return application.business.workflow_engine.run(workflow)


def test_workflow_run_query_and_resume(client, application):
    run = _start_wait_workflow(application)
    assert run.status == "WAITING"
    response = client.get(f"/v1/workflow-runs/{run.run_id}", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["status"] == "WAITING"

    resume = client.post(f"/v1/workflow-runs/{run.run_id}/resume",
                         headers=AUTH, json={"signal": "CONTINUE"})
    assert resume.status_code == 200
    assert resume.json()["status"] == "COMPLETED"


def test_workflow_resume_wrong_signal(client, application):
    run = _start_wait_workflow(application)
    response = client.post(f"/v1/workflow-runs/{run.run_id}/resume",
                           headers=AUTH, json={"signal": "WRONG"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_RESUME_SIGNAL"
