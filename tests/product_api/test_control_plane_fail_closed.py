"""Phase 18.12.5a: Control Plane version resolution fail-closed gate.

The Control Plane is the sole authoritative source of the executed agent
version.  A managed agent whose resolution fails must fail-closed (HTTP error,
no ExecutionRecord, no fallback to a default/local/latest version).  Only a
genuinely unmanaged agent (no control-plane deployment record) may fall back,
and only under an explicit dev/test policy.
"""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.api.errors import ApiError
from app.api.gateway import EnterpriseProductGateway
from tests.product_api.conftest import AUTH


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


def _execution_count(application):
    return len(application.commerce.execution_manager.store._records)


def _message(client):
    return client.post("/v1/agents/commerce_operations_agent/messages",
                       headers=AUTH, json={"message": "JP01 销量下降"})


def test_http_checksum_mismatch_fails_closed(http_app):
    application = http_app.state.application
    registry = application.control_plane.registry
    _register_artifact(registry, "commerce_operations_agent", "2.0")

    projector = application.control_plane.projector
    projection = projector.project("commerce_operations_agent", "PRODUCTION")
    projector.projections[("commerce_operations_agent", "PRODUCTION")] = (
        replace(projection, checksum="tampered-checksum"))

    before = _execution_count(application)
    client = TestClient(http_app)
    response = _message(client)
    assert response.status_code != 200
    assert _execution_count(application) == before


def test_http_inactive_agent_fails_closed(http_app):
    application = http_app.state.application
    registry = application.control_plane.registry
    _register_artifact(registry, "commerce_operations_agent", "1.0")
    registry.disable("commerce_operations_agent", "1.0")

    before = _execution_count(application)
    client = TestClient(http_app)
    response = _message(client)
    assert response.status_code == 404
    assert _execution_count(application) == before


def test_http_control_plane_resolution_error_does_not_fallback(http_app, monkeypatch):
    application = http_app.state.application
    registry = application.control_plane.registry
    _register_artifact(registry, "commerce_operations_agent", "1.0")

    def boom(agent_id):
        raise RuntimeError("unexpected control-plane failure")

    monkeypatch.setattr(registry, "get_active_artifact", boom)

    before = _execution_count(application)
    client = TestClient(http_app)
    response = _message(client)
    assert response.status_code != 200
    assert _execution_count(application) == before


def test_failed_version_resolution_creates_no_execution(http_app):
    application = http_app.state.application
    registry = application.control_plane.registry
    _register_artifact(registry, "commerce_operations_agent", "9.9",
                       activate=False)

    before = _execution_count(application)
    client = TestClient(http_app)
    response = _message(client)
    assert response.status_code != 200
    assert _execution_count(application) == before


def test_unmanaged_agent_fallback_requires_explicit_dev_test_policy(http_app):
    application = http_app.state.application
    gateway = http_app.state.gateway
    assert gateway.allow_unmanaged_agent_fallback is True

    # unmanaged + dev/test fallback -> allowed (caller uses default version)
    assert gateway._resolve_agent_version("commerce_operations_agent") is None

    # managed but resolution fails -> still denied (never misread as unmanaged)
    registry = application.control_plane.registry
    _register_artifact(registry, "commerce_operations_agent", "1.0",
                       activate=False)
    with pytest.raises(ApiError):
        gateway._resolve_agent_version("commerce_operations_agent")

    # sandbox/production policy: unmanaged fallback denied
    strict = EnterpriseProductGateway(
        agent_directory=gateway.agent_directory,
        agent_definitions=gateway.agent_definitions,
        execution_store=gateway.execution_store,
        trace_collector=gateway.trace_collector,
        approval_repository=gateway.approval_repository,
        approval_engine=gateway.approval_engine,
        workflow_repository=gateway.workflow_repository,
        workflow_engine=gateway.workflow_engine,
        fact_executor=gateway.fact_executor,
        control_plane_registry=registry,
        deployment_projector=application.control_plane.projector,
        allow_unmanaged_agent_fallback=False,
    )
    with pytest.raises(ApiError):
        strict._resolve_agent_version("not_registered_agent")
