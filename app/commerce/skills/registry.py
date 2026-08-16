"""Versioned SkillRegistry."""

from app.commerce.diagnostics.registry.base import VersionedRegistry
from app.commerce.skills.models import SkillDefinition


class SkillRegistry(VersionedRegistry):
    """Versioned skill definitions keyed by ``(skill_id, version)``."""

    def __init__(self):
        super().__init__("skill")

    def register(self, definition: SkillDefinition):
        return super().register(definition.skill_id, definition.version, definition)

    def get(self, skill_id, version=None) -> SkillDefinition:
        return super().get(skill_id, version)


__all__ = ["SkillRegistry"]
