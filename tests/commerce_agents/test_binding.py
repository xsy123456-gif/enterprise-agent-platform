"""Phase 12.2 Skill Binding tests."""

import pytest

from app.commerce.agents.binding import AgentSkillBinding, SkillBindingRegistry
from app.commerce.agents.errors import UnknownSkillForAgent
from app.commerce.skills import SkillRegistry, build_business_skill_definitions


@pytest.fixture
def skill_registry():
    registry = SkillRegistry(plan_registry=None)
    for definition in build_business_skill_definitions():
        registry.register(definition)
        registry.validate(definition.skill_id)
        registry.activate(definition.skill_id)
    return registry


def test_binding_model():
    binding = AgentSkillBinding(
        agent_id="commerce_operations_agent",
        skill_id="advertising_performance_diagnosis", skill_version="1.0",
        priority=90, routing_examples=("广告花费上涨", "ROAS下降"),
    )
    assert binding.priority == 90
    assert binding.enabled is True
    assert binding.routing_examples == ("广告花费上涨", "ROAS下降")


def test_binding_registry_validates_skill(skill_registry):
    registry = SkillBindingRegistry(skill_registry=skill_registry)
    registry.register(AgentSkillBinding(
        agent_id="a", skill_id="store_performance_diagnosis", skill_version="1.0"))
    with pytest.raises(UnknownSkillForAgent):
        registry.register(AgentSkillBinding(
            agent_id="a", skill_id="nonexistent", skill_version="1.0"))


def test_binding_registry_priority_order(skill_registry):
    registry = SkillBindingRegistry(skill_registry=skill_registry)
    registry.register(AgentSkillBinding(
        agent_id="a", skill_id="store_performance_diagnosis", skill_version="1.0",
        priority=10))
    registry.register(AgentSkillBinding(
        agent_id="a", skill_id="advertising_performance_diagnosis", skill_version="1.0",
        priority=90))
    registry.register(AgentSkillBinding(
        agent_id="a", skill_id="inventory_risk_diagnosis", skill_version="1.0",
        priority=50, enabled=False))
    ids = registry.skill_ids("a")
    assert ids == ("advertising_performance_diagnosis", "store_performance_diagnosis")


def test_agent_can_only_reach_skills_via_binding():
    # The binding registry is the sole skill gateway; there is no direct
    # tool/repository access surface on the agent layer.
    registry = SkillBindingRegistry()
    assert hasattr(registry, "skill_ids")
    assert not hasattr(registry, "query")
    assert not hasattr(registry, "execute_tool")
    assert not hasattr(registry, "repository")
