"""Phase 18.12.5 Final Hardening tests."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.platform.business.action import BusinessAction
from app.platform.business.workflow import BusinessWorkflow, WorkflowStep
from tests.product_api.conftest import AUTH, seed_commerce


class _RecordingPort:
    def __init__(self):
        self.calls = []

    def execute(self, action, context=None):
        self.calls.append((action.action_type, action.target))


def _approval_action_workflow():
    return BusinessWorkflow(
        workflow_id="replenishment", version="1.0",
        steps=[
            WorkflowStep(step_id="approval", step_type="APPROVAL",
                         name="补货审批", next_steps=("purchase",)),
            WorkflowStep(step_id="purchase", step_type="ACTION"),
        ],
    )


def _demo_action():
    return BusinessAction(
        action_id="a1", action_type="CREATE_PURCHASE_ORDER", target="sku_1",
        risk_level="LOW", status="APPROVED")


def _start_approval_workflow(application, port):
    application.business.action_runtime.execution_port = port
    return application.business.workflow_engine.run(
        _approval_action_workflow(),
        context={"action": _demo_action(), "tenant_id": "company_A"})


# ── Approval -> Workflow -> Action ─────────────────────────

def test_http_approval_resumes_workflow_and_executes_action_once(http_app):
    application = http_app.state.application
    port = _RecordingPort()
    run = _start_approval_workflow(application, port)
    assert run.status == "WAITING_APPROVAL"

    client = TestClient(http_app)
    approvals = client.get("/v1/approvals", headers=AUTH).json()["items"]
    approval_id = approvals[0]["approval_id"]

    response = client.post(f"/v1/approvals/{approval_id}/approve",
                           headers=AUTH, json={"comment": "ok"})
    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"

    finished = application.business.workflow_engine.run_repository.get(run.run_id)
    assert finished.status == "COMPLETED"
    assert port.calls == [("CREATE_PURCHASE_ORDER", "sku_1")]


def test_http_rejection_blocks_workflow_action(http_app):
    application = http_app.state.application
    port = _RecordingPort()
    run = _start_approval_workflow(application, port)
    assert run.status == "WAITING_APPROVAL"

    client = TestClient(http_app)
    approvals = client.get("/v1/approvals", headers=AUTH).json()["items"]
    approval_id = approvals[0]["approval_id"]

    response = client.post(f"/v1/approvals/{approval_id}/reject",
                           headers=AUTH, json={"comment": "no"})
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"

    finished = application.business.workflow_engine.run_repository.get(run.run_id)
    assert finished.status == "FAILED"
    assert port.calls == []


# ── Cross-tenant trace isolation ───────────────────────────

def test_cross_tenant_trace_is_not_visible(client, application):
    body = client.post("/v1/agents/commerce_operations_agent/messages",
                       headers=AUTH, json={"message": "JP01 销量下降"}).json()
    execution_id = body["execution"]["execution_id"]

    gateway = client.app.state.gateway
    other_tenant = SimpleNamespace(tenant_id="company_B", principal_id="U001")
    from app.api.errors import ApiError
    with pytest.raises(ApiError) as exc:
        gateway.get_execution_trace(other_tenant, execution_id)
    assert exc.value.code == "RESOURCE_NOT_FOUND"


# ── Unauthorized approval isolation ────────────────────────

def test_unauthorized_principal_cannot_approve(http_app):
    application = http_app.state.application
    port = _RecordingPort()
    run = _start_approval_workflow(application, port)

    def deny(trusted_context, request):
        return trusted_context.principal_id == "U002"

    gateway = http_app.state.gateway
    gateway.approval_authorizer = deny

    client = TestClient(http_app)
    approvals = client.get("/v1/approvals", headers=AUTH).json()["items"]
    approval_id = approvals[0]["approval_id"]

    # U001 is denied by the authorizer -> 403, state unchanged
    response = client.post(f"/v1/approvals/{approval_id}/approve",
                           headers=AUTH, json={"comment": "ok"})
    assert response.status_code == 403

    request = application.business.approval.repository.get(approval_id)
    assert request.status == "PENDING"
    assert application.business.workflow_engine.run_repository.get(
        run.run_id).status == "WAITING_APPROVAL"
    assert port.calls == []


# ── Control Plane active-version resolution ────────────────

def _register_artifact(registry, agent_id, version, activate=True):
    from app.platform.agent_control import AgentManifest
    from app.platform.agent_control.domain import AgentArtifact
    from app.platform.agent_control.versioning import artifact_checksum
    manifest = AgentManifest.from_dict({
        "agent_id": agent_id, "version": version, "owner": "commerce_team",
        "department": "commerce", "description": "ops",
        "skills": ("store_performance_diagnosis",),
        "required_capabilities": ("commerce.metrics.read",),
    })
    artifact = AgentArtifact(
        agent_id=agent_id, version=version, manifest=manifest,
        skills=manifest.skills, capabilities=manifest.required_capabilities,
        checksum=artifact_checksum(manifest))
    registry.register(artifact)
    registry.validate(agent_id, version)
    if activate:
        registry.activate(agent_id, version)
    return artifact


def test_http_agent_uses_active_control_plane_version(client, application):
    registry = application.control_plane.registry
    _register_artifact(registry, "commerce_operations_agent", "1.0")
    _register_artifact(registry, "commerce_operations_agent", "2.0",
                       activate=False)
    assert registry.active_version("commerce_operations_agent") == "1.0"

    first = client.post("/v1/agents/commerce_operations_agent/messages",
                        headers=AUTH, json={"message": "JP01 销量下降"}).json()
    record = application.commerce.execution_manager.store.get(
        first["execution"]["execution_id"])
    assert record.agent_version == "1.0"

    registry.activate("commerce_operations_agent", "2.0")
    second = client.post("/v1/agents/commerce_operations_agent/messages",
                         headers=AUTH, json={"message": "JP01 销量下降"}).json()
    record2 = application.commerce.execution_manager.store.get(
        second["execution"]["execution_id"])
    assert record2.agent_version == "2.0"


def test_client_cannot_pin_agent_version(client):
    response = client.post(
        "/v1/agents/commerce_operations_agent/messages",
        headers=AUTH, json={"message": "hi", "agent_version": "1.0.0"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
