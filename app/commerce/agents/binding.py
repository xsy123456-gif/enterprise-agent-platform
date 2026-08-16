"""Agent -> Skill binding (Phase 12.2).

An Agent never invokes a Skill directly; it goes through an
``AgentSkillBinding`` that pins version, priority, enablement and routing
examples.  This decoupling leaves room for per-tenant configuration, canary and
A/B in later phases.

The ``SkillBindingRegistry`` is the *only* gateway through which an Agent may
reach a Skill — an Agent has no direct access to Tools / Repository / Database.
"""

from dataclasses import dataclass

from app.commerce.agents.errors import UnknownSkillForAgent


@dataclass(frozen=True)
class AgentSkillBinding:
    agent_id: str
    skill_id: str
    skill_version: str
    priority: int = 0
    enabled: bool = True
    routing_examples: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "routing_examples", tuple(self.routing_examples or ()))
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if not self.skill_id:
            raise ValueError("skill_id is required")
        if not self.skill_version:
            raise ValueError("skill_version is required")

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "priority": self.priority,
            "enabled": self.enabled,
            "routing_examples": list(self.routing_examples),
        }


class SkillBindingRegistry:
    """Validated, versioned Agent -> Skill bindings."""

    def __init__(self, skill_registry=None):
        self.skill_registry = skill_registry
        self._bindings = {}

    def register(self, binding: AgentSkillBinding) -> AgentSkillBinding:
        if self.skill_registry is not None:
            try:
                self.skill_registry.get(binding.skill_id, binding.skill_version)
            except Exception as error:  # noqa: BLE001 - re-raised as typed error
                raise UnknownSkillForAgent(
                    f"binding references unknown skill {binding.skill_id!r}@"
                    f"{binding.skill_version!r}"
                ) from error
        self._bindings[(binding.agent_id, binding.skill_id)] = binding
        return binding

    def get(self, agent_id, skill_id):
        return self._bindings.get((agent_id, skill_id))

    def bindings_for(self, agent_id) -> list[AgentSkillBinding]:
        return sorted(
            (b for (a, _), b in self._bindings.items() if a == agent_id and b.enabled),
            key=lambda b: -b.priority,
        )

    def skill_ids(self, agent_id) -> tuple[str, ...]:
        return tuple(b.skill_id for b in self.bindings_for(agent_id))


__all__ = ["AgentSkillBinding", "SkillBindingRegistry"]
