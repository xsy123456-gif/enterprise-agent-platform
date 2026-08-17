"""Phase 13.3 Deployment Model tests."""

import pytest

from app.platform.agent_control.deployment import DeploymentManager
from app.platform.agent_control.domain import AgentArtifact
from app.platform.agent_control.errors import DeploymentError
from app.platform.agent_control.manifest import AgentManifest
from app.platform.agent_control.registry import AgentRegistry
from app.platform.agent_control.versioning import artifact_checksum


def _active_registry():
    registry = AgentRegistry()
    manifest = AgentManifest.from_dict({
        "agent_id": "commerce_agent", "version": "1.0", "owner": "commerce_team",
        "department": "marketing", "skills": ("store_diagnosis",),
        "required_capabilities": ("commerce.metrics.read",),
    })
    artifact = AgentArtifact(
        agent_id="commerce_agent", version="1.0", manifest=manifest,
        skills=manifest.skills, capabilities=manifest.required_capabilities,
        checksum=artifact_checksum(manifest))
    registry.register(artifact)
    registry.validate("commerce_agent")
    registry.activate("commerce_agent")
    return registry


def test_deploy_to_multiple_environments():
    manager = DeploymentManager(_active_registry())
    prod = manager.deploy("commerce_agent", "PRODUCTION")
    test = manager.deploy("commerce_agent", "TEST")
    assert prod.agent_version == "1.0"
    assert test.agent_version == "1.0"
    assert prod.environment == "PRODUCTION"
    assert test.environment == "TEST"
    assert manager.get("commerce_agent", "PRODUCTION") == prod


def test_deploy_non_active_agent_fails():
    registry = AgentRegistry()
    manifest = AgentManifest.from_dict({
        "agent_id": "sales_agent", "version": "1.0", "owner": "sales_team",
        "department": "sales", "skills": ("sales_diagnosis",),
        "required_capabilities": ("sales.report.read",),
    })
    artifact = AgentArtifact(
        agent_id="sales_agent", version="1.0", manifest=manifest,
        checksum=artifact_checksum(manifest))
    registry.register(artifact)  # DRAFT only, not active
    manager = DeploymentManager(registry)
    with pytest.raises(Exception):
        manager.deploy("sales_agent", "PRODUCTION")


def test_deploy_unknown_environment_fails():
    manager = DeploymentManager(_active_registry())
    with pytest.raises(DeploymentError):
        manager.deploy("commerce_agent", "MARS")


def test_disable_deployment():
    manager = DeploymentManager(_active_registry())
    manager.deploy("commerce_agent", "PRODUCTION")
    disabled = manager.disable("commerce_agent", "PRODUCTION")
    assert disabled.status == "DISABLED"
    assert manager.active_in("PRODUCTION") == []
