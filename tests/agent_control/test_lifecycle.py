"""Phase 13.2 Agent Lifecycle tests."""

import pytest

from app.platform.agent_control.domain import AgentArtifact
from app.platform.agent_control.errors import AgentValidationError
from app.platform.agent_control.lifecycle import validate_artifact, validate_manifest
from app.platform.agent_control.manifest import AgentManifest
from app.platform.agent_control.registry import AgentRegistry
from app.platform.agent_control.versioning import artifact_checksum


def _manifest(**overrides):
    data = {
        "agent_id": "finance_agent", "version": "1.0", "owner": "finance_team",
        "department": "finance", "description": "finance agent",
        "skills": ("finance_diagnosis",),
        "required_capabilities": ("finance.report.read",),
        "security_policy": "default", "evaluation_policy": "default",
    }
    data.update(overrides)
    return AgentManifest.from_dict(data)


def _artifact(**overrides):
    manifest = _manifest(**overrides)
    return AgentArtifact(
        agent_id="finance_agent", version="1.0", manifest=manifest,
        skills=manifest.skills, capabilities=manifest.required_capabilities,
        checksum=artifact_checksum(manifest))


def test_validate_manifest_requires_owner():
    with pytest.raises(AgentValidationError):
        validate_manifest(_manifest(owner=""))


def test_validate_manifest_requires_department():
    with pytest.raises(AgentValidationError):
        validate_manifest(_manifest(department=""))


def test_validate_manifest_requires_skills_and_capabilities():
    with pytest.raises(AgentValidationError):
        validate_manifest(_manifest(skills=()))
    with pytest.raises(AgentValidationError):
        validate_manifest(_manifest(required_capabilities=()))


def test_validate_artifact_ok():
    assert validate_artifact(_artifact()).agent_id == "finance_agent"


def test_registry_validate_fails_incomplete_manifest():
    registry = AgentRegistry()
    registry.register(_artifact())  # valid manifest -> checksum ok
    incomplete = _artifact(owner="")
    incomplete = AgentArtifact(
        agent_id="finance_agent", version="1.1", manifest=incomplete.manifest,
        checksum=artifact_checksum(incomplete.manifest))
    registry.register(incomplete)
    with pytest.raises(AgentValidationError):
        registry.validate("finance_agent", "1.1")
