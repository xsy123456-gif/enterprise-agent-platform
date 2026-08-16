"""Versioned SkillRegistry with a lifecycle.

A Skill moves through DRAFT -> VALIDATED -> ACTIVE; activation requires every
bound DiagnosticPlan to be ACTIVE.  Only ACTIVE skills run.
"""

from app.commerce.diagnostics.registry.base import VersionedRegistry
from app.commerce.skills.errors import SkillNotActiveError
from app.commerce.skills.models import SkillDefinition
from app.commerce.skills.validation import (
    validate_skill_capabilities,
    validate_skill_plan_consistency,
)

SKILL_DRAFT = "DRAFT"
SKILL_VALIDATED = "VALIDATED"
SKILL_ACTIVE = "ACTIVE"
SKILL_DEPRECATED = "DEPRECATED"
SKILL_DISABLED = "DISABLED"
SKILL_STATUSES = frozenset({
    SKILL_DRAFT, SKILL_VALIDATED, SKILL_ACTIVE, SKILL_DEPRECATED, SKILL_DISABLED,
})


class SkillRegistry(VersionedRegistry):
    """Versioned skills keyed by ``(skill_id, version)`` + lifecycle status."""

    def __init__(self, plan_registry=None):
        super().__init__("skill")
        self.plan_registry = plan_registry
        self._status = {}

    def register(self, definition: SkillDefinition):
        validate_skill_capabilities(definition)
        result = super().register(definition.skill_id, definition.version, definition)
        self._status[(definition.skill_id, definition.version)] = SKILL_DRAFT
        return result

    def validate(self, skill_id, version=None):
        version = self._resolve_version(skill_id, version)
        definition = self.get(skill_id, version)
        validate_skill_capabilities(definition)
        validate_skill_plan_consistency(definition, self.plan_registry)
        self._status[(skill_id, version)] = SKILL_VALIDATED
        return definition

    def activate(self, skill_id, version=None):
        version = self._resolve_version(skill_id, version)
        definition = self.get(skill_id, version)
        if self.plan_registry is not None:
            for plan_id in definition.plan_ids:
                self.plan_registry.get_active_ir(plan_id)  # raises if not ACTIVE
        self._status[(skill_id, version)] = SKILL_ACTIVE
        self._active[skill_id] = version
        return definition

    def deprecate(self, skill_id, version=None):
        version = self._resolve_version(skill_id, version)
        self._status[(skill_id, version)] = SKILL_DEPRECATED

    def disable(self, skill_id, version=None):
        version = self._resolve_version(skill_id, version)
        self._status[(skill_id, version)] = SKILL_DISABLED

    def status(self, skill_id, version=None):
        version = self._resolve_version(skill_id, version)
        return self._status[(skill_id, version)]

    def get_active_skill(self, skill_id):
        version = self._active.get(skill_id)
        if version is None:
            raise SkillNotActiveError(f"skill {skill_id!r} is not active")
        if self._status[(skill_id, version)] != SKILL_ACTIVE:
            raise SkillNotActiveError(
                f"skill {skill_id!r}@{version} is not ACTIVE "
                f"({self._status[(skill_id, version)]})"
            )
        return self._items[(skill_id, version)]

    def get(self, skill_id, version=None) -> SkillDefinition:
        return super().get(skill_id, version)

    def _resolve_version(self, skill_id, version):
        if version is not None:
            if (skill_id, version) not in self._items:
                from app.commerce.diagnostics.errors import UnknownDefinitionVersionError
                raise UnknownDefinitionVersionError(
                    f"skill {skill_id!r} has no version {version!r}"
                )
            return version
        active = self._active.get(skill_id)
        if active is not None:
            return active
        versions = self.versions(skill_id)
        if not versions:
            from app.commerce.diagnostics.errors import UnknownDefinitionError
            raise UnknownDefinitionError(f"skill {skill_id!r} is not registered")
        return versions[0]


__all__ = [
    "SkillRegistry",
    "SKILL_DRAFT",
    "SKILL_VALIDATED",
    "SKILL_ACTIVE",
    "SKILL_DEPRECATED",
    "SKILL_DISABLED",
    "SKILL_STATUSES",
]
