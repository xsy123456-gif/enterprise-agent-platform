"""Phase 13.1 Agent Registry Platform tests."""

import pytest

from app.commerce.diagnostics.errors import DuplicateDefinitionError
from app.platform.agent_control.domain import (
    AGENT_ACTIVE,
    AGENT_DRAFT,
    AGENT_VALIDATED,
    AgentArtifact,
)
from app.platform.agent_control.errors import AgentValidationError
from app.platform.agent_control.manifest import AgentManifest
from app.platform.agent_control.registry import AgentRegistry
from app.platform.agent_control.versioning import artifact_checksum


def _manifest(agent_id="commerce_agent", version="1.0", **overrides):
    data = {
        "agent_id": agent_id, "version": version, "owner": "commerce_team",
        "department": "marketing", "description": "commerce ops",
        "skills": ("store_diagnosis",),
        "required_capabilities": ("commerce.metrics.read",),
        "security_policy": "default", "evaluation_policy": "default",
    }
    data.update(overrides)
    return AgentManifest.from_dict(data)


def _artifact(agent_id="commerce_agent", version="1.0", **overrides):
    manifest = _manifest(agent_id, version, **overrides)
    return AgentArtifact(
        agent_id=agent_id, version=version, manifest=manifest,
        skills=manifest.skills, capabilities=manifest.required_capabilities,
        checksum=artifact_checksum(manifest),
    )


def test_register_and_lifecycle():
    registry = AgentRegistry()
    artifact = _artifact()
    registry.register(artifact)
    assert registry.status("commerce_agent") == AGENT_DRAFT
    registry.validate("commerce_agent")
    assert registry.status("commerce_agent") == AGENT_VALIDATED
    registry.activate("commerce_agent")
    assert registry.status("commerce_agent") == AGENT_ACTIVE
    assert registry.get_active_artifact("commerce_agent") == artifact


def test_duplicate_version_rejected():
    registry = AgentRegistry()
    registry.register(_artifact(version="1.0"))
    with pytest.raises(DuplicateDefinitionError):
        registry.register(_artifact(version="1.0"))


def test_multiple_versions_coexist_no_auto_upgrade():
    registry = AgentRegistry()
    registry.register(_artifact(version="1.0"))
    registry.register(_artifact(version="1.1"))
    assert set(registry.versions("commerce_agent")) == {"1.0", "1.1"}
    # first version is default (not auto-upgraded to 1.1)
    assert registry.get("commerce_agent").version == "1.0"


def test_activate_requires_validated():
    registry = AgentRegistry()
    registry.register(_artifact())
    with pytest.raises(AgentValidationError):
        registry.activate("commerce_agent")


def test_checksum_mismatch_rejected():
    manifest = _manifest()
    artifact = AgentArtifact(
        agent_id="commerce_agent", version="1.0", manifest=manifest,
        checksum="deadbeef")
    registry = AgentRegistry()
    with pytest.raises(AgentValidationError):
        registry.register(artifact)


def test_explicit_activation_promotes_version():
    registry = AgentRegistry()
    registry.register(_artifact(version="1.0"))
    registry.register(_artifact(version="1.1"))
    registry.validate("commerce_agent", "1.0")
    registry.activate("commerce_agent", "1.0")
    registry.validate("commerce_agent", "1.1")
    registry.activate("commerce_agent", "1.1")
    assert registry.get_active_artifact("commerce_agent").version == "1.1"
