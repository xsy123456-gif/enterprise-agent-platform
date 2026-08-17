"""Phase 12.1 Agent Domain Model tests."""

from pathlib import Path

import pytest

from app.commerce.agents import (
    AGENT_ACTIVE,
    AGENT_DEPRECATED,
    AGENT_DRAFT,
    AGENT_VALIDATED,
    KNOWN_AGENT_CAPABILITY_IDS,
    AgentDefinition,
    AgentManifest,
    AgentRequest,
    AgentResponse,
    AgentSession,
    AgentValidationError,
    UnknownSkillForAgent,
    validate_agent,
)
from app.commerce.agents.domain import (
    RESPONSE_DIAGNOSTIC,
    RESPONSE_TYPES,
    SESSION_STATUSES,
)
from app.commerce.skills import SkillRegistry, build_business_skill_definitions

ROOT = Path(__file__).resolve().parents[2]


def _definition(agent_id="commerce_operations_agent"):
    return AgentDefinition(
        agent_id=agent_id, version="1.0",
        name="Commerce Operations Employee",
        description="AI assistant for ecommerce operators",
    )


def _manifest(agent_id="commerce_operations_agent",
              skills=("store_performance_diagnosis",),
              default_skill="store_performance_diagnosis",
              capabilities=("commerce.metrics.read",)):
    return AgentManifest(
        agent_id=agent_id, version="1.0", description="ops agent",
        skills=skills, default_skill=default_skill,
        required_capabilities=capabilities,
    )


@pytest.fixture
def skill_registry():
    registry = SkillRegistry(plan_registry=None)
    for definition in build_business_skill_definitions():
        registry.register(definition)
        registry.validate(definition.skill_id)
        registry.activate(definition.skill_id)
    return registry


# ── AgentDefinition ─────────────────────────────────────────

def test_agent_definition_valid():
    definition = _definition()
    assert definition.agent_id == "commerce_operations_agent"
    assert definition.version == "1.0"
    assert definition.status == AGENT_DRAFT


def test_agent_definition_forbidden_fields():
    definition = _definition()
    for forbidden in ("prompt", "tools", "permissions",
                      "runtime_state", "conversation"):
        assert not hasattr(definition, forbidden)
    data = definition.to_dict()
    for forbidden in ("prompt", "tools", "permissions"):
        assert forbidden not in data


def test_agent_definition_invalid_status():
    with pytest.raises(ValueError):
        AgentDefinition(agent_id="a", version="1.0", name="n", description="d",
                        status="RUNNING")


def test_agent_definition_round_trip():
    definition = _definition()
    assert AgentDefinition.from_dict(definition.to_dict()) == definition


# ── AgentSession ────────────────────────────────────────────

def test_agent_session_valid_and_no_identity():
    session = AgentSession(session_id="s1", agent_id="commerce_operations_agent")
    assert session.status == "CREATED"
    assert not hasattr(session, "tenant_id")
    assert not hasattr(session, "principal_id")


def test_agent_session_invalid_status():
    with pytest.raises(ValueError):
        AgentSession(session_id="s1", agent_id="a", status="NOPE")


# ── AgentRequest ────────────────────────────────────────────

def test_agent_request_forbidden_identity_fields():
    request = AgentRequest.from_dict({
        "request_id": "r1", "message": "hi",
        "tenant_id": "evil", "principal_id": "hacker",
        "role": "admin", "permission": "all", "scope": "everything",
    })
    for forbidden in ("tenant_id", "principal_id", "role", "permission", "scope"):
        assert not hasattr(request, forbidden)
    assert request.to_dict() == {
        "request_id": "r1", "session_id": "", "message": "hi",
        "attachments": [], "trace_id": "",
    }


# ── AgentResponse ───────────────────────────────────────────

def test_agent_response_types():
    response = AgentResponse(response_id="resp1", response_type=RESPONSE_DIAGNOSTIC)
    assert response.response_type in RESPONSE_TYPES
    with pytest.raises(ValueError):
        AgentResponse(response_id="resp1", response_type="BANANA")


# ── AgentManifest ───────────────────────────────────────────

def test_manifest_from_yaml():
    manifest = AgentManifest.from_yaml(
        "agent_id: commerce_operations_agent\n"
        "version: 1.0\n"
        "description: ops\n"
        "skills:\n  - store_performance_diagnosis\n"
        "default_skill: store_performance_diagnosis\n"
        "required_capabilities:\n  - commerce.metrics.read\n"
    )
    assert manifest.agent_id == "commerce_operations_agent"
    assert manifest.version == "1.0"
    assert manifest.skills == ("store_performance_diagnosis",)


def test_manifest_from_yaml_invalid():
    from app.commerce.agents.errors import AgentManifestError
    with pytest.raises(AgentManifestError):
        AgentManifest.from_yaml("not: [valid")


def test_manifest_from_dict_missing_agent_id():
    from app.commerce.agents.errors import AgentManifestError
    with pytest.raises(AgentManifestError):
        AgentManifest.from_dict({"version": "1.0"})


# ── Lifecycle validation ────────────────────────────────────

def test_validate_manifest_structure_no_skills():
    with pytest.raises(AgentValidationError):
        validate_agent(_definition(), _manifest(skills=()))


def test_validate_manifest_structure_bad_default():
    with pytest.raises(AgentValidationError):
        validate_agent(_definition(), _manifest(default_skill="other_skill"))


def test_validate_agent_unknown_skill(skill_registry):
    manifest = _manifest(skills=("nonexistent_skill",),
                         default_skill="nonexistent_skill")
    with pytest.raises(UnknownSkillForAgent):
        validate_agent(_definition(), manifest, skill_registry=skill_registry)


def test_validate_agent_unknown_capability():
    manifest = _manifest(capabilities=("commerce.fake.read",))
    with pytest.raises(AgentValidationError):
        validate_agent(_definition(), manifest,
                       known_capability_ids=KNOWN_AGENT_CAPABILITY_IDS)


def test_sample_manifest_file_is_valid(skill_registry):
    path = (ROOT / "app" / "commerce" / "agents" / "manifests"
            / "commerce_operations_agent.yaml")
    manifest = AgentManifest.from_yaml(path.read_text(encoding="utf-8"))
    assert manifest.agent_id == "commerce_operations_agent"
    assert "daily_operations_triage" in manifest.skills
    validate_agent(_definition(), manifest, skill_registry=skill_registry,
                   known_capability_ids=KNOWN_AGENT_CAPABILITY_IDS)


# ── AgentRegistry lifecycle ─────────────────────────────────

def test_agent_registry_lifecycle(skill_registry):
    from app.commerce.agents.registry import AgentRegistry
    registry = AgentRegistry(
        skill_registry=skill_registry,
        known_capability_ids=KNOWN_AGENT_CAPABILITY_IDS,
    )
    definition = _definition()
    manifest = _manifest()
    registry.register(definition, manifest)
    assert registry.status(definition.agent_id) == AGENT_DRAFT
    with pytest.raises(AgentValidationError):
        registry.activate(definition.agent_id)
    registry.validate(definition.agent_id)
    assert registry.status(definition.agent_id) == AGENT_VALIDATED
    registry.activate(definition.agent_id)
    assert registry.status(definition.agent_id) == AGENT_ACTIVE
    assert registry.get_active_agent(definition.agent_id) == definition
    registry.deprecate(definition.agent_id)
    assert registry.status(definition.agent_id) == AGENT_DEPRECATED


def test_agent_registry_validate_requires_manifest(skill_registry):
    from app.commerce.agents.registry import AgentRegistry
    registry = AgentRegistry(skill_registry=skill_registry)
    registry.register(_definition())
    with pytest.raises(AgentValidationError):
        registry.validate("commerce_operations_agent")
