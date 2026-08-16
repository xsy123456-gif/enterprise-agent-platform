"""Employee agent composition root (Phase 12.8).

``build_employee_agent_runtime`` wires the frozen building blocks — SkillBinding
gateway, SkillRouter (rule + entity + llm), ResponseBuilder and
ConversationManager — into a runnable employee agent.  The agent still only
reaches Skills through the binding registry, and business reasoning still comes
from the Diagnostic Kernel, never from the LLM.
"""

from app.commerce.agents.binding import SkillBindingRegistry
from app.commerce.agents.conversation import ConversationManager
from app.commerce.agents.response import ResponseBuilder
from app.commerce.agents.router import (
    EntityRouter,
    LLMRouter,
    RuleRouter,
    SkillRouter,
    keyword_map_from_bindings,
)


def build_employee_agent_runtime(agent_definition, manifest, skill_system,
                                 skill_bindings, llm=None, memory_port=None,
                                 knowledge_port=None, knowledge_enabled=False,
                                 known_subjects=None,
                                 execution_adapter=None) -> ConversationManager:
    binding_registry = SkillBindingRegistry(
        skill_registry=getattr(skill_system, "skill_registry", None))
    for binding in skill_bindings:
        binding_registry.register(binding)

    rule_router = RuleRouter(keyword_map_from_bindings(
        binding_registry.bindings_for(agent_definition.agent_id)))
    entity_router = EntityRouter(known_subjects=known_subjects) if known_subjects else None
    llm_router = LLMRouter(llm=llm) if llm else None
    router = SkillRouter(rule_router=rule_router, entity_router=entity_router,
                         llm_router=llm_router)

    return ConversationManager(
        agent_definition=agent_definition, manifest=manifest,
        binding_registry=binding_registry, skill_system=skill_system,
        router=router, response_builder=ResponseBuilder(llm=llm),
        memory_port=memory_port, knowledge_port=knowledge_port,
        knowledge_enabled=knowledge_enabled,
        execution_adapter=execution_adapter,
    )


__all__ = ["build_employee_agent_runtime"]
