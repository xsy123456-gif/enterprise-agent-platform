"""Phase 18.4 Registry Convergence tests (Deployment Projection)."""

import pytest

from app.platform.agent_control import (
    AgentDeploymentProjector,
    AgentManifest,
    AgentRegistry,
)
from app.platform.agent_control.domain import AgentArtifact
from app.platform.agent_control.errors import DeploymentVersionMismatchError
from app.platform.agent_control.versioning import artifact_checksum
from app.commerce.agents.registry import AgentRegistry as CommerceAgentRegistry


def _control_plane_artifact():
    manifest = AgentManifest.from_dict({
        "agent_id": "commerce_operations_agent", "version": "1.0",
        "owner": "commerce_team", "department": "commerce",
        "description": "commerce ops", "skills": ("store_performance_diagnosis",),
        "required_capabilities": ("commerce.metrics.read",),
    })
    return AgentArtifact(
        agent_id="commerce_operations_agent", version="1.0", manifest=manifest,
        skills=manifest.skills, capabilities=manifest.required_capabilities,
        checksum=artifact_checksum(manifest))


def _active_control_plane():
    registry = AgentRegistry()
    registry.register(_control_plane_artifact())
    registry.validate("commerce_operations_agent")
    registry.activate("commerce_operations_agent")
    return registry


def test_projector_projects_into_commerce_registry():
    control = _active_control_plane()
    commerce = CommerceAgentRegistry()
    projector = AgentDeploymentProjector(control, commerce_agent_registry=commerce)
    projection = projector.project("commerce_operations_agent", "PRODUCTION")
    assert projection.version == "1.0"
    assert projection.checksum
    # the application projection now has an ACTIVE commerce agent definition
    definition = commerce.get_active_agent("commerce_operations_agent")
    assert definition.agent_id == "commerce_operations_agent"
    assert definition.version == "1.0"


def test_projector_version_mismatch_fails():
    control = _active_control_plane()
    projector = AgentDeploymentProjector(control)
    with pytest.raises(DeploymentVersionMismatchError):
        projector.project("commerce_operations_agent", "PRODUCTION", version="9.9")


def test_projector_verify_checksum():
    control = _active_control_plane()
    artifact = control.get("commerce_operations_agent")
    projector = AgentDeploymentProjector(control)
    assert projector.verify("commerce_operations_agent", "1.0", artifact.checksum)
    with pytest.raises(DeploymentVersionMismatchError):
        projector.verify("commerce_operations_agent", "1.0", "tampered-checksum")
